# تعديلات النشر السحابي

## الملفات
- استبدل `app/retrieval/store.py` بهذا الإصدار.
- استبدل `app/core/config.py` بهذا الإصدار.
- استبدل `app/retrieval/retriever.py` بهذا الإصدار.
- استبدل `requirements.txt` بهذا الإصدار.
- أضف `index.py` في جذر المشروع.
- أضف `sql/supabase_schema.sql`.

## تعديلان صغيران في `app/main.py`
1. غيّر الاستيراد:
   `from app.retrieval.store import ChromaStore`
   إلى:
   `from app.retrieval.store import SupabaseVectorStore`
2. غيّر:
   `store = ChromaStore()`
   إلى:
   `store = SupabaseVectorStore()`
3. استيراد الإعدادات يصبح:
   `from app.core.config import DATA_DIR, REPO_DATA_DIR`
4. داخل endpoint `/ingest`، قبل `build_documents(...)`، اختر مجلد البيانات هكذا:
   ```python
   ingest_data_dir = DATA_DIR
   if not (DATA_DIR / tenant_id).exists() and (REPO_DATA_DIR / tenant_id).exists():
       ingest_data_dir = REPO_DATA_DIR
   ```
   ثم استخدم `data_dir=ingest_data_dir` في استدعاء `build_documents` الخاص بـ `/ingest` فقط.

## 1) Supabase
1. افتح https://supabase.com/dashboard وأنشئ مشروعًا مجانيًا.
2. افتح SQL Editor ثم الصق ونفّذ كامل ملف `sql/supabase_schema.sql`.
3. من Connect اختر اتصال PostgreSQL مناسبًا للتطبيقات السحابية (Transaction Pooler)، وانسخ URI.
4. احتفظ بالـ URI وكلمة المرور؛ لا تضعهما في GitHub أو Streamlit.

## 2) إعداد محلي
1. حدّث `.env` المحلي بإضافة `SUPABASE_DB_URL` و`GEMINI_API_KEY` و`GEMINI_MODEL` و`GEMINI_EMBEDDING_MODEL` من `.env.example`.
2. ثبّت المتطلبات: `pip install -r requirements.txt`.
3. شغّل `python run.py`.
4. افتح `/docs`، واختر `admin_demo` حسب واجهة المصادقة الحالية، وارفع ملفات PDF من `/upload` أو من واجهة Streamlit كي تُعاد فهرستها في Supabase. قاعدة ChromaDB القديمة لن تنتقل تلقائيًا.
5. شغّل الاختبارات: `python -m pytest -q`.

## 3) GitHub
راجع `git status` وتأكد أن `.env` وملفات البيانات السرية غير مضافة، ثم:
```powershell
git add -A
git diff --cached --check
git status
git commit -m "Move RAG storage to Supabase pgvector"
git push origin main
```

## 4) Vercel Backend
1. افتح https://vercel.com/new واختر مستودع `Financial-Compliance-Agent`.
2. اترك Root Directory على جذر المستودع.
3. أضف Environment Variables:
   - `SUPABASE_DB_URL`
   - `GEMINI_API_KEY`
   - `GEMINI_MODEL` = `gemini-3.6-flash`
   - `GEMINI_EMBEDDING_MODEL` = `gemini-embedding-001`
   - `TOP_K` = `8`
   - `RERANK_K` = `5`
   - `MIN_EVIDENCE_SCORE` = `0.18`
4. Deploy. اختبر `https://YOUR-VERCEL-DOMAIN/health` ثم `/docs`.
5. ارفع/أعد فهرسة ملفات PDF بعد النشر؛ قاعدة ChromaDB القديمة غير مستوردة إلى Supabase.

## 5) Streamlit Frontend
1. افتح https://share.streamlit.io/ ثم أنشئ/افتح التطبيق من `frontend/app.py` والفرع `main`.
2. في App settings → Secrets أضف:
   ```toml
   API_URL = "https://YOUR-VERCEL-DOMAIN"
   ```
3. تأكد أن جميع طلبات `POST /chat` و`POST /upload` ترسل `headers={"X-Demo-User": selected_demo_user}` لأن الـ Backend الحالي يطلب هذا الهيدر.
4. جرّب رفع ملف PDF ثم سؤالًا عن نفس الملف.

## ملاحظات مهمة
- هذا الإصدار يستبدل ChromaDB المحلي بـ Supabase Postgres/pgvector، ويستعمل Gemini Embeddings API بدل تنزيل نموذج BGE محليًا.
- ملفات PDF المرفوعة تُقرأ وتُفهرس ضمن طلب الرفع؛ الملفات الأصلية ليست مخزنة بشكل دائم على Vercel. الفهرس والنصوص والـ vectors تستمر في Supabase. أعد رفع الملف إذا احتجت إلى إعادة فهرسته.
- حسابات `*_demo` آلية تجريبية وليست مصادقة إنتاجية؛ لا تستخدم ملفات مالية سرية أو بيانات عملاء حقيقية مع هذا النموذج.

### التعديل المطلوب في `frontend/app.py`
استبدل تعريف `API_URL` ببلوك يقرأ secrets أولًا، وأضف اختيار المستخدم:
```python
try:
    configured_api_url = st.secrets["API_URL"]
except Exception:
    configured_api_url = os.getenv("API_URL", "http://127.0.0.1:8000")

API_URL = st.sidebar.text_input("API URL", configured_api_url).rstrip("/")
demo_user = st.sidebar.selectbox(
    "Demo user",
    ["admin_demo", "analyst_demo", "manager_demo", "auditor_demo", "company_b_analyst"],
)
request_headers = {"X-Demo-User": demo_user}
```
ثم أضف `headers=request_headers,` داخل استدعائي `requests.post` الخاصين بـ `/upload` و`/chat`.
