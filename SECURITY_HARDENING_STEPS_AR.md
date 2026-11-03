# طريقة تطبيق النسخة المعدّلة بأقل مخاطرة

## أ) قبل أي تغيير

1. خذ نسخة احتياطية من `E:\Financial Complince Agent`.
2. لا تحذف قاعدة Supabase أو جدول `compliance_chunks`.
3. لا ترفع `.env` أو ملفات أسرار.

## ب) استبدال الملفات

1. فك ضغط حزمة `Financial-Compliance-Agent-Security-Patch.zip` فوق مجلد المشروع الحالي.
2. وافق على استبدال الملفات عند السؤال، مع الحفاظ على المجلدات النسبية.
3. لا تغيّر `AUTH_MODE` من `demo` الآن.
4. نفّذ:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```

المتوقع في هذه الحزمة: `17 passed`.

## ج) تحديث Supabase قبل إعادة نشر Backend

1. افتح Supabase → SQL Editor.
2. شغّل `sql/supabase_schema.sql` مرة واحدة.
3. شغّل `sql/rls_smoke_test.sql` وتأكد أن استعلام مستخدم `tenant_b` لا يرى صفوف `tenant_demo`.
4. لا تنشئ حسابات حقيقية بعد إن لم تكن مستعدًا. يمكنك أولًا إعادة تشغيل الوضع التجريبي على ملفات Demo فقط.

## د) انشر الكود مع بقاء Demo مؤقتًا

1. ارفع الملفات المعدّلة إلى GitHub.
2. أعد نشر Backend على SnapDeploy.
3. أعد نشر Streamlit أو ادفع نسخة الواجهة.
4. اترك `AUTH_MODE=demo` في الطرفين مؤقتًا. اختبر Demo PDFs فقط.

## هـ) إعداد JWT عند جاهزية Supabase Auth

اتبع كل خطوات `docs/AUTHENTICATION_SETUP_AR.md` لإنشاء حسابات Auth وإضافة سجلات `compliance_user_access`.

بعد ذلك غيّر إعدادات Backend في SnapDeploy إلى:

```text
AUTH_MODE=supabase_jwt
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_PUBLISHABLE_OR_ANON_KEY
SUPABASE_DB_URL=YOUR_POSTGRES_CONNECTION_STRING
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

واضبط Streamlit Secrets على القيم التالية فقط:

```toml
AUTH_MODE = "supabase_jwt"
API_URL = "https://YOUR-BACKEND-HOST"
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_ANON_KEY = "YOUR_PUBLISHABLE_OR_ANON_KEY"
```

**ممنوع** وضع `SUPABASE_DB_URL` أو `GEMINI_API_KEY` أو service_role key في Streamlit أو GitHub.

## و) اختبارات بعد التفعيل

- `GET /me` بلا Bearer token → `401`.
- تسجيل دخول مسؤول Pilot → `/me` يعرض الـ tenant والدور المسجلين في DB.
- محلل Pilot يحاول `POST /ingest` أو `/upload` → `403`.
- محلل `tenant_pilot` لا يرى أي مستند من Tenant آخر.
- مستند access_scope=`roles` ومسموح لـ manager لا يظهر للمحلل.
- أوقف حسابًا من `compliance_user_access` بوضع `is_active=false`؛ يفقد الوصول بعد التحقق التالي.

## ز) متى تسمح ببيانات شركة؟

ليس بعد تطبيق JWT وحده. انظر `docs/DATA_SECURITY_REVIEW_AR.md`: يلزم نقل PDF الأصلي إلى private persistent object storage، وعدم استخدام Streamlit Community Cloud للبيانات المالية/الحساسة، واستخدام معالجة Gemini مدفوعة بعقد/DPA معتمد أو نموذج داخل بيئة الشركة، وتطبيق سياسة احتفاظ وحذف ونسخ احتياطي.
