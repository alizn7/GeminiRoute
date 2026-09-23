<div align="center">

<img src="https://raw.githubusercontent.com/alizn7/GeminiRoute/main/docs/banner.svg" alt="GeminiRoute" width="100%">

[![verified routes](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge.json)](https://alizn7.github.io/GeminiRoute/sub/best.txt)
[![exit countries](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-countries.json)](https://alizn7.github.io/GeminiRoute/)
[![verified of tested](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-success.json)](https://alizn7.github.io/GeminiRoute/api/stats.json)
[![rebuilt hourly](https://img.shields.io/github/actions/workflow/status/alizn7/GeminiRoute/discovery.yml?style=flat-square&label=rebuilt%20hourly&labelColor=1f2d3a)](https://github.com/alizn7/GeminiRoute/actions)
[![license](https://img.shields.io/badge/license-MIT-1f2d3a?style=flat-square)](LICENSE)

[English](README.md) &nbsp;·&nbsp; **فارسی**

### خط لوله‌ای خودکار که مسیرهای شبکه را کشف، اعتبارسنجی و رتبه‌بندی می‌کند.<br>هر ساعت روی GitHub Actions اجرا می‌شود و آنچه را که دوام بیاورد منتشر می‌کند.

![Python 3.12](https://img.shields.io/badge/Python%203.12-3776AB?style=flat-square&logo=python&logoColor=white)
![asyncio](https://img.shields.io/badge/asyncio-1f2d3a?style=flat-square)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)
![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-222?style=flat-square&logo=github&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Xray core](https://img.shields.io/badge/Xray%20core-1f2d3a?style=flat-square)
![Typer](https://img.shields.io/badge/Typer-1f2d3a?style=flat-square)
![httpx](https://img.shields.io/badge/httpx-1f2d3a?style=flat-square)
![Ruff](https://img.shields.io/badge/Ruff-D7FF64?style=flat-square&logo=ruff&logoColor=white)
![Mypy](https://img.shields.io/badge/Mypy-1f2d3a?style=flat-square)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=flat-square&logo=pytest&logoColor=white)

[**استفاده**](#start) &nbsp;·&nbsp; [**چطور کار می‌کند**](#engineering) &nbsp;·&nbsp; [**وضعیت زنده**](https://alizn7.github.io/GeminiRoute/) &nbsp;·&nbsp; [**اجرای محلی**](#dev)

</div>

<a id="start"></a>

## 🚀 از اینجا شروع کنید

<div dir="rtl">

**۱.** این لینک را کپی کنید

</div>

```
https://alizn7.github.io/GeminiRoute/sub/best.txt
```

<div dir="rtl">

**۲.** برنامه‌تان را باز کنید و به بخش **Subscriptions** بروید — بعضی برنامه‌ها
اسمش را *Profiles* یا *Groups* گذاشته‌اند

**۳.** یک اشتراک جدید بسازید، لینک را paste کنید، به‌روزرسانی بزنید و وصل شوید

همین. حساب کاربری و ثبت‌نام لازم نیست. فهرست هر ساعت خودش بازسازی می‌شود، پس
تنها کاری که باید هر از گاهی بکنید زدن دکمهٔ *update* در برنامه است.

### 📱 &nbsp; کدام برنامه؟

| برنامه | سیستم | کجا paste کنید |
|:--|:--|:--|
| [**v2rayN**](https://github.com/2dust/v2rayN) | ویندوز · مک · لینوکس | Subscriptions → Add |
| [**v2rayNG**](https://github.com/2dust/v2rayNG) | اندروید | Subscription settings → **+** |
| [**NekoBox**](https://github.com/MatsuriDayo/NekoBoxForAndroid) | اندروید | Groups → **+** → Subscription |
| [**Hiddify**](https://github.com/hiddify/hiddify-next) | همهٔ سیستم‌ها | New profile → From URL |
| [**Streisand**](https://apps.apple.com/app/streisand/id6450534064) · [**V2Box**](https://apps.apple.com/app/v2box-v2ray-client/id6446814690) | آیفون | Add subscription |
| [**sing-box**](https://github.com/SagerNet/sing-box) | همهٔ سیستم‌ها | هر مبدل اشتراک |

> ### ⚠️ اگر Gemini گفت کشور شما پشتیبانی نمی‌شود
>
> **ممکن است ایراد از نود نباشد.** نسخهٔ وب Gemini علاوه بر IP، کشور حساب
> گوگلی را هم که در مرورگر وارد شده‌اید بررسی می‌کند — و هیچ پراکسی‌ای آن را
> عوض نمی‌کند.
>
> `gemini.google.com` را در یک پنجرهٔ **ناشناس و خارج‌شده از حساب** باز کنید.
> اگر آنجا بالا آمد، مسدودیت از حساب شماست نه از نود.

</div>

<a id="links"></a>

## 🔗 همهٔ لینک‌ها

<div align="center">

[![best](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-sub-best.json)](#best) &nbsp; [![all verified](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-sub-gemini.json)](#gemini) &nbsp; [![fast](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-sub-fast.json)](#fast) &nbsp; [![everything](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-sub-all.json)](#all)

<sub>عددها هر ساعت به‌روز می‌شوند</sub>

</div>

<a id="best"></a>

### 🎯 &nbsp; بهترین‌ها &nbsp;·&nbsp; از اینجا شروع کنید

<div dir="rtl">

۳۰ نود با بالاترین امتیاز، هر ساعت دوباره رتبه‌بندی می‌شوند.

</div>

```
https://alizn7.github.io/GeminiRoute/sub/best.txt
```

<a id="gemini"></a>

### ✅ &nbsp; همهٔ تأییدشده‌ها

<div dir="rtl">

هر نودی که تست را رد کرده، به ترتیب امتیاز. اگر `best` جواب نداد، این را
امتحان کنید.

</div>

```
https://alizn7.github.io/GeminiRoute/sub/gemini.txt
```

<a id="fast"></a>

### ⚡ &nbsp; سریع

<div dir="rtl">

تأییدشده **و** زیر ۵۰۰ میلی‌ثانیه. تعدادش کمتر است ولی سریع‌تر وصل می‌شود.

</div>

```
https://alizn7.github.io/GeminiRoute/sub/fast.txt
```

<a id="all"></a>

### 📦 &nbsp; همه چیز

<div dir="rtl">

هر نودی که تست شده، تأییدشده یا نه. برای استفاده‌ای غیر از Gemini.

</div>

```
https://alizn7.github.io/GeminiRoute/sub/all.txt
```

<div dir="rtl">

<sub>اگر به‌جای <code>.txt</code> بنویسید <code>.plain.txt</code>، نسخه‌ای می‌گیرید که base64 نشده است.</sub>

</div>

---

### 🌍 &nbsp; فقط یک کشور

```
https://alizn7.github.io/GeminiRoute/sub/country/<code>.txt
```

<div dir="rtl">

بیست کشور از اجراهای اخیر، هرکدام یک اشتراک کامل. این فهرست هر ساعت عوض
می‌شود — [صفحهٔ وضعیت](https://alizn7.github.io/GeminiRoute/) نسخهٔ جاری را دارد.

</div>

|   |   |   |   |   |
|:-:|:-:|:-:|:-:|:-:|
| [🇺🇸 `us`](https://alizn7.github.io/GeminiRoute/sub/country/us.txt) | [🇳🇱 `nl`](https://alizn7.github.io/GeminiRoute/sub/country/nl.txt) | [🇩🇪 `de`](https://alizn7.github.io/GeminiRoute/sub/country/de.txt) | [🇫🇷 `fr`](https://alizn7.github.io/GeminiRoute/sub/country/fr.txt) | [🇵🇱 `pl`](https://alizn7.github.io/GeminiRoute/sub/country/pl.txt) |
| [🇫🇮 `fi`](https://alizn7.github.io/GeminiRoute/sub/country/fi.txt) | [🇬🇧 `gb`](https://alizn7.github.io/GeminiRoute/sub/country/gb.txt) | [🇸🇬 `sg`](https://alizn7.github.io/GeminiRoute/sub/country/sg.txt) | [🇮🇹 `it`](https://alizn7.github.io/GeminiRoute/sub/country/it.txt) | [🇭🇰 `hk`](https://alizn7.github.io/GeminiRoute/sub/country/hk.txt) |
| [🇯🇵 `jp`](https://alizn7.github.io/GeminiRoute/sub/country/jp.txt) | [🇨🇦 `ca`](https://alizn7.github.io/GeminiRoute/sub/country/ca.txt) | [🇪🇸 `es`](https://alizn7.github.io/GeminiRoute/sub/country/es.txt) | [🇹🇷 `tr`](https://alizn7.github.io/GeminiRoute/sub/country/tr.txt) | [🇪🇪 `ee`](https://alizn7.github.io/GeminiRoute/sub/country/ee.txt) |
| [🇸🇪 `se`](https://alizn7.github.io/GeminiRoute/sub/country/se.txt) | [🇳🇴 `no`](https://alizn7.github.io/GeminiRoute/sub/country/no.txt) | [🇰🇷 `kr`](https://alizn7.github.io/GeminiRoute/sub/country/kr.txt) | [🇦🇺 `au`](https://alizn7.github.io/GeminiRoute/sub/country/au.txt) | [🇮🇳 `in`](https://alizn7.github.io/GeminiRoute/sub/country/in.txt) |

---

### 📈 &nbsp; برای برنامه‌ها

<div align="center">

[![stats.json](https://img.shields.io/badge/api-stats.json-1f2d3a?style=flat-square)](https://alizn7.github.io/GeminiRoute/api/stats.json)
&nbsp;
[![nodes.json](https://img.shields.io/badge/api-nodes.json-1f2d3a?style=flat-square)](https://alizn7.github.io/GeminiRoute/api/nodes.json)

</div>

<div dir="rtl">

فایل `stats.json` قیف، تفکیک کشوری و بازده هر منبع را دارد. `nodes.json` هر نود
تست‌شده را با امتیاز و کشور خروجش دارد، بدون هیچ اطلاعات محرمانه‌ای.

</div>

<a id="engineering"></a>

## 🏗 چطور کار می‌کند

<div align="center">

<img src="https://alizn7.github.io/GeminiRoute/card.svg" alt="قیف آخرین اجرا" width="100%">

</div>

<div dir="rtl">

هر ساعت پانزده هزار کاندیدا می‌رسد و چند صد تا دوام می‌آورد. بیشتر فهرست‌ها
بازمانده‌ها را منتشر می‌کنند؛ عدد جالب این است که چه چیزی دور ریخته شد و کجا —
و برای همین قیف بالا اولین چیزی است که در صفحهٔ وضعیت می‌بینید.

</div>

```
collect → parse → normalize → dedup → plausibility → connect
        → exit check → Gemini → score → publish
```

<div dir="rtl">

هر مرحله یک پکیج است که از مراحل اطرافش بی‌خبر است. پکیج `core/` هیچ چیزی جز
کتابخانهٔ استاندارد ایمپورت نمی‌کند، و همین باعث می‌شود کل خط لوله بدون شبکه و
بدون دیتابیس قابل تست باشد.

چیزها در محیط واقعی خراب می‌شوند. وقتی خراب شدند، نوشته می‌شوند:
[گزارش حوادث](docs/incidents/).

### تصمیم‌هایی که واقعاً فرق ایجاد کردند

هرکدام از این‌ها از اندازه‌گیری‌ای درآمد که خلاف انتخاب بدیهی را نشان داد.

**مرتب‌سازی بر اساس تأخیر، سرورهای مرده را انتخاب می‌کند.** وقتی کاندیداهای
قابل‌دسترس بیشتر از ظرفیت مرحلهٔ گران‌اند، حرکت بدیهی این است که سریع‌ترین‌ها
اول تست شوند. نتیجه‌اش انتخاب لبه‌های CDN جلوی سرورهای مرده است: در چند
میلی‌ثانیه handshake را تمام می‌کنند و هیچ‌چیز را پراکسی نمی‌کنند. اضافه شدن یک
منبع پر از این کانفیگ‌ها نرخ موفقیت را نصف کرد در حالی که میانگین handshake از
۲۰۹ به ۸۵ میلی‌ثانیه **بهتر** شد. حالا اول نودهای اثبات‌شده و بعد بقیه به‌صورت
تصادفی انتخاب می‌شوند — که پوشش را هم می‌چرخاند، پس کل استخر در حدود شش ساعت
دیده می‌شود به‌جای اینکه هر ساعت همان زیرمجموعه تست شود.

**از تونل بپرس کجا خارج می‌شود، نه از کانفیگ.** مکان‌یابی آدرس کانفیگ، لبهٔ CDN
جلوی آن را گزارش می‌کند. یک بار سی نود با برچسب کانادا منتشر شدند در حالی که از
جایی خارج می‌شدند که Gemini سرویس نمی‌دهد. حالا از هر کاندیدا، از داخل تونل
خودش، محل خروج واقعی‌اش پرسیده می‌شود — و همان هم پرچم منتشرشده را تعیین می‌کند
و هم اینکه نود کلاً رد شود یا نه.

**از خود باینری بپرس چه چیزی را قبول می‌کند.** نسخه‌های Xray سر «کانفیگ معتبر»
اختلاف دارند؛ `allowInsecure` سال‌ها پذیرفته می‌شد و نسخه‌های جدید ردش می‌کنند.
کانفیگ ردشده به‌عنوان شکست نود ثبت می‌شود و از نود مرده قابل تشخیص نیست — در یک
اجرا ۱۳۹ نود به همین دلیل شکست خوردند بدون اینکه راهی برای فهمیدنش باشد. حالا
خط لوله یک بار در هر اجرا از باینری می‌پرسد، و دستور `geminiroute xray-check`
هر ۲۱ شکل کانفیگی را که تولید می‌کند به باینری نصب‌شده می‌دهد و می‌گوید کدام‌ها
پذیرفته می‌شوند.

**قرارداد «هرگز پرتاب نکن» جایش سطح batch است.** یک کانفیگ SNIی داشت که کدک
`idna` قبولش نمی‌کند. خطای `UnicodeError` زیرکلاس `ValueError` است، پس از
دست هندلرهای سوکت و TLS در رفت و اجرایی با ۱۰٬۶۷۱ نود را سر نود ۳٬۰۰۰اُم از پا
درآورد. شمردن نوع استثناها در هر نقطهٔ فراخوانی همیشه سوراخ دارد؛ حالا تضمین یک
بار در سطح batch داده می‌شود.

**منابع بر اساس بازده اندازه‌گیری‌شده نگه داشته می‌شوند، نه شهرت.** تأییدشده
تقسیم بر قابل‌دسترس: منابعی که ماندند بین ۱۷٪ تا ۶۶٪ هستند و هر منبعی که حذف شد
زیر ۳٪ بود، آن هم با دسترسی TCP **بهتر**. سه تا از فهرست‌های ردشده از یک
رتبه‌بندی بالادستی آمدند که منابع را بر اساس دسترسی TCP امتیاز می‌دهد — دقیقاً
همان ویژگی‌ای که کارکرد نود را پیش‌بینی نمی‌کند. حالا `geminiroute try-source`
یک کاندیدا را با یک نمونه در حدود دو دقیقه می‌سنجد.

<details>
<summary><b>امتیازدهی، زمان‌بندی و خروجی</b></summary>

<br>

امتیازدهی: تأخیر ۳۰٪، تأیید ۳۰٪، پایداری در سی روز گذشته ۲۵٪ و کیفیت handshake
۱۵٪. نودی که سابقه ندارد در پایداری ۰.۵ می‌گیرد — نامعلوم، نه بد — پس نودهای
تازه از وسط جدول شروع می‌کنند.

نودی که شکست بخورد بلافاصله دوباره تست نمی‌شود: اول ۵ دقیقه، بعد ۳۰ دقیقه، بعد
ساعت‌ها تا یک سقف روزانه. سه شکست پشت سر هم یعنی مرده، و نود مرده پس از پایان
مهلتش دوباره وارد استخر می‌شود. بدون این، نودهایی که سه اجرا پشت سر هم شکست
خورده‌اند همچنان هر ساعت یک جا را اشغال می‌کردند.

دیتابیس SQLite به‌صورت یک فایل فشرده روی ریلیز `db-state` بین اجراها جابه‌جا
می‌شود، چون runner بعد از هر اجرا نابود می‌شود؛ بدون آن تاریخچهٔ پایداری هر ساعت
صفر می‌شد. اینکه چرا آنجا و نه داخل گیت: فایلی با این حجم که هر ساعت بازنویسی
می‌شود تاریخچهٔ شاخه را باد می‌کند و بالاخره به سقف ۱۰۰ مگابایتی گیت‌هاب
می‌خورد — که یک بار خورد، و
[گزارشش اینجاست](docs/incidents/2026-09-22-database-size-limit.md).

برچسب هر کانفیگ منتشرشده به `<n>.<flag> GeminiRoute` بازنویسی می‌شود. فقط برچسب
عوض می‌شود — چون بازتولید کانفیگ از روی فیلدهای پارس‌شده، هر پارامتری را که
مدل ما نمایندگی نمی‌کند بی‌صدا حذف می‌کرد.

</details>

<details>
<summary><b>داخل ریپو چه چیزی هست</b></summary>

<br>

| | |
|:--|:--|
| **۱۵ پکیج** | `core`، `parsing`، `normalization`، `collection`، `dedup`، `validation`، `scoring`، `reliability`، `retry`، `storage`، `generation`، `orchestration`، `observability`، `config` |
| **۲۷۸ تست** | تست واحد به‌علاوهٔ تست یکپارچگی روی سوکت و سرور HTTP واقعی محلی — بدون کتابخانهٔ mock |
| **دو workflow** | `ci.yml` روی هر pull request ابزار Ruff، Mypy و pytest را روی پایتون ۳.۱۲ و ۳.۱۳ اجرا می‌کند؛ `discovery.yml` خط لوله را ساعتی می‌دواند و روی GitHub Pages منتشر می‌کند |
| **هشت دستور CLI** | اجرای خط لوله به‌علاوهٔ ابزار تشخیص: `doctor`، `errors`، `sources`، `try-source`، `xray-check`، `probe-node` |
| **وابستگی‌ها** | دو تا در زمان اجرا. جمع‌آوری، پارس، اتصال، مکان‌یابی، امتیازدهی، ذخیره‌سازی و تولید خروجی همه کتابخانهٔ استانداردند |
| **گزارش حوادث** | [نوشتهٔ کامل خرابی‌هایی](docs/incidents/) که به محیط واقعی رسیدند |

</details>

</div>

<a id="faq"></a>

## ❓ سؤال‌ها

<div dir="rtl">

<details>
<summary><b>برنامه‌ام چیزی import نکرد یا می‌گوید سروری نیست</b></summary>

<br>

مطمئن شوید لینک را در بخش **subscription** گذاشته‌اید، نه اینکه آن را به‌عنوان
یک کانفیگ تکی باز کرده باشید. اگر باز چیزی نشان نداد، نسخهٔ `.plain.txt` را
امتحان کنید — بعضی برنامه‌های قدیمی‌تر اشتراک base64 را رمزگشایی نمی‌کنند.

</details>

<details>
<summary><b>سرور وصل می‌شود ولی چیزی بالا نمی‌آید</b></summary>

<br>

هر نود اینجا از یک runner در کشوری که گوگل سرویس می‌دهد تأیید شده. این ثابت
می‌کند نود به Gemini می‌رسد، ولی نمی‌تواند ثابت کند از **شبکهٔ شما** قابل دسترس
است — این تنها بخشی است که از CI قابل تست نیست. یکی دیگر از فهرست را امتحان
کنید؛ دقیقاً برای همین بیشتر از یکی منتشر می‌شود.

</details>

<details>
<summary><b>واقعاً رایگان است؟ ایرادش کجاست؟</b></summary>

<br>

رایگان، بدون حساب، بدون ردیابی. هیچ‌کدام از این سرورها متعلق به این پروژه نیست —
کانفیگ‌های عمومی‌اند که دیگران منتشر کرده‌اند و اینجا جمع و تست می‌شوند. ایرادش
ذاتی خودشان است: سرور عمومی رایگان مشترک است، غیرقابل پیش‌بینی است، و ممکن است
از این ساعت تا ساعت بعد ناپدید شود. دقیقاً برای همین هر ساعت بازسازی می‌شود.

</details>

<details>
<summary><b>می‌شود برای چیزی غیر از Gemini استفاده کرد؟</b></summary>

<br>

بله — این‌ها کانفیگ‌های معمولی پراکسی‌اند. فقط **تست**شان با Gemini انجام
می‌شود، پس «تأییدشده» اینجا معنای مشخصی دارد، و نودی که آن تست را رد نکند ممکن
است برای بقیهٔ کارها کاملاً خوب باشد. `sub/all.txt` برای همین است.

</details>

</div>

<a id="dev"></a>

## 🛠 اجرای محلی

```bash
git clone https://github.com/alizn7/GeminiRoute.git && cd GeminiRoute
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

ruff check . && mypy geminiroute && pytest
```

<div dir="rtl">

مرحلهٔ اعتبارسنجی به باینری [Xray](https://github.com/XTLS/Xray-core/releases)
روی `PATH` نیاز دارد، یا `XRAY_PATH` را ست کنید. بقیهٔ مراحل بدون آن هم اجرا
می‌شوند.

فهرست کامل دستورها، افزودن منبع و تنظیمات در
[نسخهٔ انگلیسی](README.md#dev) هست.

</div>

## ⚠️ محدودیت‌های واقعی

<div dir="rtl">

این‌ها **سرورهای دیگران‌اند** که خودکار جمع‌آوری شده‌اند. هیچ‌چیز اینجا توسط این
پروژه اداره نمی‌شود، و یک پراکسی عمومی رایگان می‌تواند ترافیک شما را ببیند —
برای هر چیزی که برایتان مهم است از رمزنگاری سرتاسری استفاده کنید و وارد حسابی
نشوید که از دست دادنش برایتان گران تمام می‌شود.

اعتبارسنجی از یک runner گیت‌هاب در کشوری که گوگل سرویس می‌دهد انجام می‌شود. این
ثابت می‌کند نود به Gemini می‌رسد، ولی ثابت نمی‌کند از **شبکهٔ شما** قابل دسترس
است — تنها بخشی که از CI قابل تست نیست.

برای پژوهش و برای رسیدن به اینترنت آزاد در جایی که محدود شده منتشر شده است. به
قوانینی که بر شما اعمال می‌شود پایبند باشید.

</div>

---

<div align="center">
<sub>MIT licensed · built in the open · <a href="https://alizn7.github.io/GeminiRoute/">وضعیت زنده</a></sub>
</div>
