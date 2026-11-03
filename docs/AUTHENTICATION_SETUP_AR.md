# إعداد تسجيل الدخول الحقيقي JWT خطوة بخطوة

> **مهم:** الوضع الافتراضي في الكود ما زال `AUTH_MODE=demo` حتى لا تتوقف النسخة الحالية. لا تغيّر إلى `supabase_jwt` إلا بعد تطبيق SQL وإنشاء حسابات وربطها، ثم ضبط Backend وStreamlit معًا.

## 0) خذ نسخة احتياطية

- انسخ مجلد المشروع قبل استبدال الملفات.
- لا ترفع `.env` أو كلمات المرور أو `SUPABASE_DB_URL` أو أي Service Role/Secret Key إلى GitHub.
- جرّب أولًا على مشروع Supabase تجريبي وليس قاعدة بيانات شركة.

## 1) نفّذ مخطط قاعدة البيانات وRLS

1. افتح Supabase Dashboard ثم اختر مشروعك.
2. افتح **SQL Editor → New query**.
3. افتح `sql/supabase_schema.sql` من المشروع.
4. انسخ محتواه كاملًا إلى SQL Editor واضغط **Run** مرة واحدة.
5. تأكد من ظهور الجدولين:
   - `public.compliance_chunks`
   - `public.compliance_user_access`
6. تأكد من تفعيل RLS على الجدولين. المخطط يفعّل RLS ويفرضه، ويزيل صلاحيات `anon`، ويمنح `authenticated` الصلاحيات الضرورية فقط مع سياسات منفصلة للقراءة والإضافة والتعديل والحذف.

لا تحذف الجدول الحالي ولا تعِد إنشاءه. السكربت يستخدم `CREATE TABLE IF NOT EXISTS` ويستبدل السياسات المسماة الخاصة بالمشروع.

## 2) فعّل تسجيل الدخول بالبريد وكلمة المرور

1. من Supabase افتح **Authentication → Providers → Email**.
2. فعّل Email provider.
3. أنشئ حسابات المستخدمين يدويًا من **Authentication → Users → Add user** أو Invite user.
4. للشركة الحقيقية، عطّل التسجيل العام إذا كان الموظفون يجب أن يُضافوا بدعوة فقط، واضبط تأكيد البريد وسياسة كلمات المرور بما يتفق مع الشركة.
5. فعّل MFA إذا كانت سياسة الشركة تتطلب ذلك.

## 3) أنشئ حسابات Pilot

أنشئ مثلًا حسابين تجريبيين:

- مسؤول: `pilot-admin@your-company.example`
- محلل: `pilot-analyst@your-company.example`

انسخ **User UID** من كل مستخدم. لا تستخدم البريد الإلكتروني مكان UUID.

## 4) اربط المستخدمين بالـ Tenant والأدوار

في SQL Editor نفّذ الإدخالات بعد استبدال UUIDs. مثال مسؤول ومحلل داخل الشركة التجريبية `tenant_pilot`:

```sql
insert into public.compliance_user_access
    (auth_user_id, tenant_id, roles, permissions, is_active)
values
(
    'UUID-OF-PILOT-ADMIN',
    'tenant_pilot',
    array['admin'],
    array[
        'documents:read',
        'documents:write',
        'compliance:analyze',
        'audit:read',
        'users:manage'
    ],
    true
),
(
    'UUID-OF-PILOT-ANALYST',
    'tenant_pilot',
    array['analyst'],
    array['documents:read', 'compliance:analyze'],
    true
);
```

ملاحظات:
- كل Auth user له سجل واحد وTenant واحد في النسخة الحالية.
- الأدوار المقبولة: `admin`, `analyst`, `manager`, `auditor`.
- الصلاحيات المسموحة محددة في قيود الجدول. لا تضف صلاحية غير موجودة دون تحديث المخطط والكود والاختبارات.
- لا تخزن `tenant_id` أو الدور أو الصلاحيات في `user_metadata` الذي يستطيع المستخدم تعديله. المصدر المعتمد هنا هو `compliance_user_access` على الخادم.
- لإيقاف حساب دون حذفه: حدّث `is_active = false`.

للتحقق من الربط:

```sql
select auth_user_id, tenant_id, roles, permissions, is_active
from public.compliance_user_access
order by tenant_id, roles;
```

## 5) اضبط متغيرات Backend

في إعدادات خدمة SnapDeploy (أو منصة Backend الخاصة بك) أضف:

```text
AUTH_MODE=supabase_jwt
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_PUBLISHABLE_OR_ANON_KEY
SUPABASE_DB_URL=YOUR_POSTGRES_CONNECTION_STRING
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-3.6-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
MAX_UPLOAD_BYTES=20971520
```

`SUPABASE_DB_URL` و`GEMINI_API_KEY` أسرار Backend فقط. استخدم Connection string الموصى به في Supabase، واحتفظ بـ SSL مفعّل. لا تنسخ القيم الحقيقية إلى هذا الدليل أو GitHub.

## 6) اضبط Streamlit Secrets

**تنبيه مهم:** استخدم Streamlit Community Cloud للاختبارات بالمستندات المصطنعة فقط. شروط Community Cloud تمنع معالجة المعلومات المالية أو المعلومات الشخصية الحساسة، كما تقيّد معالجة البيانات الشخصية في سياق تجاري. قبل أي Pilot ببيانات شركة أو مستندات مالية، انقل الواجهة إلى استضافة خاصة/مؤسسية وافقت عليها الشركة.

للاختبار بالمستندات الاصطناعية فقط، في **Streamlit Community Cloud → App → Settings → Secrets** أضف فقط:

```toml
AUTH_MODE = "supabase_jwt"
API_URL = "https://YOUR-BACKEND-HOST"
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_ANON_KEY = "YOUR_PUBLISHABLE_OR_ANON_KEY"
```

لا تضع في Streamlit:
- `SUPABASE_DB_URL`
- `GEMINI_API_KEY`
- Supabase `service_role` أو Secret API key

الـ publishable/anon key مصمم للاستخدام في العميل، لكن أمان البيانات يعتمد على Auth وRLS، وليس على إخفائه.

## 7) اختبر محليًا قبل النشر

في `.env` المحلي ضع المتغيرات المطلوبة، مع `AUTH_MODE=supabase_jwt`. أعد تشغيل Backend وStreamlit.

1. افتح Streamlit وسجّل الدخول بحساب المسؤول.
2. يجب أن تعرض الواجهة UUID المستخدم والـ Tenant والدور الذي رجع من `/me`.
3. ارفع PDF تجريبيًا أو افهرس مستندات Pilot.
4. سجّل الخروج.
5. ادخل بحساب المحلل.
6. اسأل سؤالًا عن المستند.
7. جرّب زر الرفع؛ الواجهة قد تخفيه بحسب الصلاحية، لكن الاختبار الأمني الحقيقي يكون باستدعاء API مباشرة والتأكد من `403`.

## 8) اختبارات API المطلوبة

- بدون Authorization Bearer: يجب أن يرجع `/me` و`/chat` و`/upload` و`/ingest` حالة `401`.
- Token غير صالح/منتهي: `401`.
- مستخدم Auth صحيح بلا سجل نشط في `compliance_user_access`: `403`.
- المحلل بلا `documents:write` يحاول `/ingest` أو `/upload`: `403`.
- مستخدم من `tenant_b` يطلب `tenant_demo`: `403` قبل الوصول للبيانات.
- محلل في Tenant نفسه يسأل عن مستند `roles` مقيّد بـ `manager`: لا يحصل على أي chunk منه.
- جرّب الوصول عبر Data API بمفتاح anon: لا يجب أن يستطيع قراءة `compliance_chunks` أو `compliance_user_access` مباشرة.

يوجد اختبار دخان لـ RLS في `sql/rls_smoke_test.sql`. شغّله في SQL Editor بعد تطبيق المخطط، وقارن النتائج بالتعليقات داخله.

## 9) قبل ربط الواجهة بشركة

- لا تستخدم Streamlit Community Cloud لمعالجة مستندات مالية أو بيانات شركة حقيقية. شغّل Streamlit داخل بيئة الشركة أو خدمة مؤسسية راجعتها الشركة ووافقت عليها.
- لا تعتبر SnapDeploy تخزينًا دائمًا للـ PDFs؛ ملفات الحاوية المحلية تُفقد عند إعادة التشغيل. انقل ملفات PDF إلى private object storage (مثل S3/R2/Supabase Storage الخاص) مع سياسات وصول وحذف. هذا التكامل لم يُنفّذ في هذه الحزمة بعد.
- اعتمد سياسة الاحتفاظ والحذف والنسخ الاحتياطية، واختر Gemini API مدفوعًا مرتبطًا بـ Cloud Billing بعد مراجعة DPA؛ أو استخدم LLM/Embeddings داخل بيئة الشركة.
- راجع ملف `docs/DATA_SECURITY_REVIEW_AR.md` قبل الموافقة على أي بيانات حقيقية.

## 10) الرجوع إلى Demo عند الحاجة

للتطوير المحلي فقط، غيّر `AUTH_MODE=demo` في Backend وStreamlit معًا وأعد تشغيلهما. لا تستخدم Demo mode مع مستندات شركة؛ أي شخص يستطيع إرسال `X-Demo-User: admin_demo` يستطيع انتحال هوية Demo.

## ملاحظة عن التحقق

الكود يطلب من Supabase Auth التحقق من Access Token عبر `/auth/v1/user` في كل طلب API محمي، ثم يقرأ سجل الصلاحيات من قاعدة البيانات. هذا تحقق خادمي وليس فك JWT يدويًا أو الثقة ببيانات الواجهة. يلزم اختبار الاتصال الفعلي بمشروع Supabase الخاص بك بعد إدخال المتغيرات وتطبيق SQL.
