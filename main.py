import asyncio
import random
import string
import re
import requests
from playwright.async_api import async_playwright

# عنوان بريد FaucetPay المحدد لاستلام الأرباح لكل الحسابات
FAUCETPAY_EMAIL = "abdo2003islam@gmail.com"

# تحديد عدد المتصفحات التي تعمل في نفس الوقت (5 كحد أقصى لمنع الضغط واستهلاك الموارد)
CONCURRENCY_LIMIT = 5
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

def generate_random_username():
    """توليد اسم مستخدم عشوائي من 10 حروف (كبيرة وصغيرة)"""
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for _ in range(10))

def get_temporary_email():
    """إنشاء بريد مؤقت وجلسة مستقلة من Gorilla Mail"""
    try:
        response = requests.get("https://api.guerrillamail.com/ajax.php?f=get_email_address", timeout=10)
        data = response.json()
        return data['email_addr'], data['sid_token']
    except Exception as e:
        print(f"[-] خطأ في إنشاء البريد المؤقت: {e}")
        return None, None

def get_verification_link(sid_token):
    """التحقق من صندوق الوارد الخاص بالبريد المؤقت واستخراج رابط التحقق بدقة"""
    try:
        url = f"https://api.guerrillamail.com/ajax.php?f=get_email_list&offset=0&sid_token={sid_token}"
        response = requests.get(url, timeout=10).json()
        emails = response.get('list', [])
        for email_item in emails:
            mail_id = email_item.get('mail_id')
            if mail_id:
                msg_url = f"https://api.guerrillamail.com/ajax.php?f=fetch_email&email_id={mail_id}&sid_token={sid_token}"
                msg_response = requests.get(msg_url, timeout=10).json()
                body = msg_response.get('mail_body', '')
                link_match = re.search(r'https?://[^\s<>"]+verify-email[^\s<>"]+', body)
                if link_match:
                    return link_match.group(0).rstrip('"\'.)')
    except Exception as e:
        print(f"[-] خطأ أثناء جلب البريد: {e}")
    return None

async def worker(task_id):
    """دالة تمثل دورة حياة حساب واحد مستقل بالكامل مع حماية الـ Semaphore"""
    async with semaphore:
        # تأخير ثانية واحدة بين فتح كل صفحة وأخرى لتنظيم الطلبات
        await asyncio.sleep(1)
        
        email, sid_token = get_temporary_email()
        if not email:
            print(f"[المهمة {task_id}] [✘] فشل الحصول على بريد مؤقت، تخطي هذه الحاوية.")
            return

        username = generate_random_username()
        password = "ABDObarika16102003"
        print(f"[المهمة {task_id}] [+] اسم المستخدم: {username} | البريد: {email}")

        async with async_playwright() as p:
            # تشغيل المتصفح في الخلفية (headless=True) مع معاملات الأمان لسحابة غيت هب
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu"
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # رفع المهلة الافتراضية إلى 60 ثانية لحماية العمل من بطء الاستجابة
            page.set_default_timeout(60000)

            try:
                print(f"[المهمة {task_id}] [+] الانتقال إلى صفحة التسجيل...")
                await page.goto("https://faucy.app/register", timeout=60000)

                # التخلص من نافذة الخصوصية إن وجدت
                try:
                    cookie_btn_selector = 'button#accept-btn'
                    await page.wait_for_selector(cookie_btn_selector, timeout=5000)
                    await page.click(cookie_btn_selector)
                except:
                    pass

                # 1. ملء نموذج التسجيل
                await page.fill('#username', username)
                await page.fill('#email', email)
                await page.fill('#password', password)
                await page.fill('#password_confirmation', password)

                # 2. النقر على زر Register
                await page.click('button[type="submit"]:has-text("Register")')

                # 3. النقر على زر Claim now الأول
                first_claim_selector = 'a[href="https://faucy.app/faucet"]:has-text("Claim now")'
                await page.wait_for_selector(first_claim_selector, timeout=25000)
                await page.click(first_claim_selector)

                # 4. النقر على زر Claim now الثاني
                second_claim_selector = 'button[type="submit"]:has-text("Claim now")'
                await page.wait_for_selector(second_claim_selector, timeout=25000)
                await page.click(second_claim_selector)

                # 5. الانتظار قليلاً ثم النقر على Cash out
                await asyncio.sleep(5)
                cash_out_selector = 'a[href="https://faucy.app/withdraw"]:has-text("Cash out")'
                await page.wait_for_selector(cash_out_selector, timeout=25000)
                await page.click(cash_out_selector)

                # 6. طلب إرسال بريد التفعيل
                await page.wait_for_load_state("networkidle")
                verify_email_selector = 'button:has-text("Send verification email")'
                await page.wait_for_selector(verify_email_selector, timeout=25000)
                await page.click(verify_email_selector)
                print(f"[المهمة {task_id}] [✔] تم إرسال طلب التفعيل، في انتظار البريد...")

                # 7. جلب رابط التفعيل الخاص بهذا البريد حصرياً
                verification_link = None
                for attempt in range(25):
                    await asyncio.sleep(5)
                    verification_link = get_verification_link(sid_token)
                    if verification_link:
                        break

                if verification_link:
                    # فتح رابط التفعيل في تبويب جديد داخل نفس سياق الحساب (تم تصحيح الـ timeout)
                    verify_page = await context.new_page()
                    await verify_page.goto(verification_link, timeout=60000)

                    # 8. إدخال بريد FaucetPay وطلب السحب
                    wallet_input_selector = 'input[name="destination"]'
                    await verify_page.wait_for_selector(wallet_input_selector, timeout=25000)
                    await verify_page.fill(wallet_input_selector, FAUCETPAY_EMAIL)

                    request_withdraw_selector = 'button:has-text("Request withdrawal")'
                    await verify_page.click(request_withdraw_selector)
                    print(f"[المهمة {task_id}] [✔✔] تمت العملية بنجاح تام وتم السحب للحساب رقم {task_id}!")
                else:
                    print(f"[المهمة {task_id}] [✘] انتهت المهلة ولم يُستلم البريد.")

            except Exception as e:
                print(f"[المهمة {task_id}] [✘] حدث خطأ أثناء التنفيذ: {e}")
            finally:
                await browser.close()

async def main():
    num_tasks = 20  # عدد الحسابات المطلوبة
    cycle = 1
    while True:
        print(f"\n========================================")
        print(f"[*] بدء الدورة رقم ({cycle}) لـ {num_tasks} متصفحاً بالتوازي المنظم...")
        print(f"========================================")
        
        # تشغيل المهام بالتوازي المنظم عبر الـ Semaphore
        await asyncio.gather(*(worker(i+1) for i in range(num_tasks)))
        
        print(f"[*] انتهت الدورة رقم ({cycle}). جاري الاستعداد لبدء الدورة الجديدة فوراً...")
        cycle += 1
        await asyncio.sleep(10)  # استراحة قصيرة بين الدورات لتفريغ الذاكرة

if __name__ == "__main__":
    asyncio.run(main())
