import asyncio
import random
import string
import re
import requests
from playwright.async_api import async_playwright

# إعدادات البريد الأساسية
FAUCETPAY_EMAIL = "abdo2003islam@gmail.com"

# تحديد عدد المتصفحات التي تعمل في نفس الوقت (5 كحد أقصى لمنع الضغط)
CONCURRENCY_LIMIT = 5
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

def generate_random_username():
    """توليد اسم مستخدم عشوائي من 10 حروف (كبيرة وصغيرة)"""
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for _ in range(10))

def get_temporary_email():
    """إنشاء بريد مؤقت ومستقل عبر Gorilla Mail"""
    try:
        response = requests.get("https://api.guerrillamail.com/ajax.php?f=get_email_address", timeout=10)
        data = response.json()
        return data['email_addr'], data['sid_token']
    except Exception as e:
        print(f"[X] خطأ في جلب البريد المؤقت: {e}")
        return None, None

async def run_single_account(account_id):
    async with semaphore:
        # تأخير ثانية واحدة بين فتح كل صفحة وأخرى لتنظيم الطلبات
        await asyncio.sleep(1)
        
        # توليد البيانات الخاصة بهذه الجلسة
        username = generate_random_username()
        email, sid_token = get_temporary_email()
        
        if not email:
            print(f"[X] تخطي الحساب {account_id} لعدم توفر البريد.")
            return

        async with async_playwright() as p:
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
            context = await browser.new_context()
            page = await context.new_page()
            
            # رفع المهلة إلى 60 ثانية لحماية العمل من بطء الاستجابة
            page.set_default_timeout(60000)
            
            try:
                print(f"[+] بدء العمل على الحساب رقم {account_id} | اسم المستخدم: {username}")
                
                # الانتقال إلى موقع faucy.app
                await page.goto("https://faucy.app", wait_until="domcontentloaded")
                
                # ==========================================
                # أكمل هنا خطوات الأتمتة الخاصة بك داخل المتصفح:
                # مثال: تعبئة حقول التسجيل، النقر على زر الإرسال، تفعيل البريد...
                # ==========================================
                
                print(f"[✓] نجاح العملية للحساب رقم: {account_id}")
                
            except Exception as e:
                print(f"[X] حدث خطأ في الحساب {account_id}: {str(e)}")
            finally:
                await browser.close()

async def main():
    # تشغيل 20 حساباً بالتوازي المنظم
    tasks = [run_single_account(i) for i in range(1, 21)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
