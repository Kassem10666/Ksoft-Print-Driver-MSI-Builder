================================================================================
   PRINTER MSI PACKAGE BUILDER - STANDALONE EXE EDITION
   WINDOWS SERVER 2025 DEPLOYMENT PACKAGE
================================================================================

[ARABIC] دليل التثبيت والتشغيل والإزالة الكاملة
--------------------------------------------------------------------------------
تم تحويل الأداة بالكامل إلى ملف تنفيذي مستقل بصيغة EXE:
[PrinterMSIBuilder.exe]
لا تحتاج إلى تثبيت بايثون ولا أي مكتبات ولا أي أدوات خارجية إطلاقاً!

1. التشغيل المباشر:
   - فقط اضغط مرتين على [PrinterMSIBuilder.exe] وسيعمل السيرفر فوراً على المنفذ 5000.

2. التثبيت كخدمة دائمة على السيرفر (24/7):
   - انقر بزر الفأرة الأيمن على [Install-Server2025.bat] واختر "Run as administrator".
   - سيقوم بفتح بورت 5000 في جدار الحماية وتسجيل الخدمة لتعمل تلقائياً في خلفية
     السيرفر حتى مع إعادة تشغيل السيرفر.

3. حذف وإلغاء تثبيت الحزمة بالكامل (Uninstall & Clean All):
   - انقر بزر الفأرة الأيمن على [Uninstall-CompleteClean.bat] واختر "Run as administrator".
   - سيقوم بإيقاف كافة العمليات وحذف الخدمة وحذف رول جدار الحماية وتنظيف الملفات
     المؤقتة، ويسألك إذا كنت ترغب في حذف المجلد بالكامل من السيرفر.

الوصول إلى الموقع:
- من نفس السيرفر: http://localhost:5000
- من أي جهاز على شبكة الشركة: http://<SERVER_IP>:5000


--------------------------------------------------------------------------------
[ENGLISH] Standalone EXE Guide & Complete Uninstallation
--------------------------------------------------------------------------------
This edition is 100% compiled into a standalone Windows executable:
[PrinterMSIBuilder.exe]
Zero Python or external dependencies are required.

1. Direct Run:
   - Double-click [PrinterMSIBuilder.exe] to start the server immediately on port 5000.

2. Install as Background Service (24/7):
   - Right-click [Install-Server2025.bat] and select "Run as administrator".
   - Opens firewall port 5000 and registers the service to start automatically on boot.

3. Complete Wipeout & Uninstallation:
   - Right-click [Uninstall-CompleteClean.bat] and select "Run as administrator".
   - Stops processes, removes the scheduled task, deletes firewall rules, and cleans up.
================================================================================
