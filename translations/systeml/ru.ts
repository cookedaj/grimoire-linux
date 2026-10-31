<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="ru" sourcelanguage="en">
<context>
    <name>grimoire.spells.systeml.alerts</name>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} uses the most ({size} GB).</source>
        <translation>Больше всего занимает {app} ({size} ГБ).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>SystemL alerts work</source>
        <translation>Оповещения SystemL работают</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>This is how memory, temperature, disk and stuck-app alerts will look.</source>
        <translation>Так будут выглядеть оповещения о памяти, температуре, дисках и зависших приложениях.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>RAM is {percent}% used ({used} of {total} GB).</source>
        <translation>ОЗУ занята на {percent}% ({used} из {total} ГБ).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>Memory almost full</source>
        <translation>Память почти заполнена</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>CPU is running hot</source>
        <translation>Процессор перегревается</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>CPU temperature is {now}°C (alert at {limit}°C).</source>
        <translation>Температура процессора {now}°C (оповещение при {limit}°C).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>GPU is running hot</source>
        <translation>Видеокарта перегревается</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>GPU temperature is {now}°C (alert at {limit}°C).</source>
        <translation>Температура видеокарты {now}°C (оповещение при {limit}°C).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{mount} is almost full</source>
        <translation>{mount} почти заполнен</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{mount} has {free} GB free ({percent}%; alert below {limit}).</source>
        <translation>На {mount} свободно {free} ГБ ({percent}%; оповещение ниже {limit}).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} isn&apos;t responding</source>
        <translation>{app} не отвечает</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>An app isn&apos;t responding</source>
        <translation>Приложение не отвечает</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>It hasn&apos;t responded for %n min. Wait a little, or close it from its window or SystemL&apos;s Processes.</source>
        <translation>
            <numerusform>Оно не отвечает уже %n мин. Подождите немного или закройте его из его окна либо в разделе «Процессы» SystemL.</numerusform>
            <numerusform>Оно не отвечает уже %n мин. Подождите немного или закройте его из его окна либо в разделе «Процессы» SystemL.</numerusform>
            <numerusform>Оно не отвечает уже %n мин. Подождите немного или закройте его из его окна либо в разделе «Процессы» SystemL.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} is stuck</source>
        <translation>{app} завис</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} (PID {pid}) has waited on a disk or device for %n min without progress, often a frozen network share or USB drive.</source>
        <translation>
            <numerusform>{app} (PID {pid}) уже %n мин ждёт диск или устройство без продвижения — часто это зависший сетевой ресурс или USB-накопитель.</numerusform>
            <numerusform>{app} (PID {pid}) уже %n мин ждёт диск или устройство без продвижения — часто это зависший сетевой ресурс или USB-накопитель.</numerusform>
            <numerusform>{app} (PID {pid}) уже %n мин ждёт диск или устройство без продвижения — часто это зависший сетевой ресурс или USB-накопитель.</numerusform>
        </translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.alertview</name>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Memory</source>
        <translation>Память</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when RAM use goes above</source>
        <translation>Предупреждает, когда занятость ОЗУ превышает</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>CPU temperature</source>
        <translation>Температура процессора</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when the CPU gets hotter than</source>
        <translation>Предупреждает, когда процессор нагревается выше</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>GPU temperature</source>
        <translation>Температура видеокарты</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when the graphics card gets hotter than</source>
        <translation>Предупреждает, когда видеокарта нагревается выше</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Stuck apps</source>
        <translation>Зависшие приложения</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when a window stays &quot;Not Responding&quot; in KWin, or one of your processes hangs on a disk or device with no progress, for</source>
        <translation>Предупреждает, когда окно остаётся «Не отвечает» в KWin или ваш процесс без продвижения висит на диске или устройстве дольше, чем</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>min</source>
        <translation>мин</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Test notification sent</source>
        <translation>Тестовое уведомление отправлено</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Couldn&apos;t send a notification: is the notification service running?</source>
        <translation>Не удалось отправить уведомление: работает ли служба уведомлений?</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Send test notification</source>
        <translation>Отправить тестовое уведомление</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Background alerts</source>
        <translation>Фоновые оповещения</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>While a problem lasts, remind again after</source>
        <translation>Пока проблема сохраняется, напоминать снова через</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Alerts</source>
        <translation>Оповещения</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Disk free space</source>
        <translation>Свободное место на дисках</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Recent alerts</source>
        <translation>Недавние оповещения</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>When</source>
        <translation>Когда</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Alert</source>
        <translation>Оповещение</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Details</source>
        <translation>Подробности</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Nothing yet. Alerts show up here (and as notifications) when something crosses a line.</source>
        <translation>Пока ничего. Оповещения появятся здесь (и в виде уведомлений), когда что-то выйдет за порог.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>On: checked once a minute, even while SystemL is closed. Each alert notifies once, then waits until it clears or the reminder time passes.</source>
        <translation>Включено: проверка раз в минуту, даже когда SystemL закрыт. Каждое оповещение приходит один раз, затем ждёт, пока проблема не исчезнет или не пройдёт время напоминания.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Off. Turn on to get notified in the background (adds a small systemd timer that runs once a minute).</source>
        <translation>Выключено. Включите, чтобы получать уведомления в фоне (добавляется небольшой таймер systemd, который срабатывает раз в минуту).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>{value} now</source>
        <translation>сейчас {value}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>no CPU sensor found, so it stays quiet</source>
        <translation>датчик процессора не найден, поэтому оповещений не будет</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>no GPU sensor found, so it stays quiet</source>
        <translation>датчик видеокарты не найден, поэтому оповещений не будет</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>No disks found.</source>
        <translation>Диски не найдены.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>{device} · {free} free of {total} · warns when free space drops below</source>
        <translation>{device} · свободно {free} из {total} · предупреждает, когда свободного места меньше</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>on</source>
        <translation>включено</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>off</source>
        <translation>выключено</translation>
    </message>
    <message>
        <source>{free} free of {total}</source>
        <translation type="vanished">свободно {free} из {total}</translation>
    </message>
    <message>
        <source>warns when free space drops below</source>
        <translation type="vanished">предупреждает, когда свободного места меньше</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.drives</name>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Drive actions need python3-dbus: {command}</source>
        <translation>Для действий с дисками нужен python3-dbus: {command}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>not allowed (polkit refused)</source>
        <translation>не разрешено (polkit отказал)</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>it&apos;s in use: close the files and apps using it, then try again</source>
        <translation>он используется: закройте файлы и приложения, которые с ним работают, и попробуйте снова</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>udisks2 isn&apos;t running</source>
        <translation>udisks2 не запущен</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>USB drive</source>
        <translation>USB-накопитель</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Hard drive</source>
        <translation>Жёсткий диск</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Optical drive</source>
        <translation>Оптический привод</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Memory card</source>
        <translation>Карта памяти</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Virtual disk</source>
        <translation>Виртуальный диск</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>not a udisks device</source>
        <translation>это не устройство udisks</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>the system runs from it, so it stays mounted</source>
        <translation>с него работает система, поэтому он остаётся подключённым</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>unmounted</source>
        <translation>отключён</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>the system runs from this drive</source>
        <translation>с этого диска работает система</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>safe to unplug</source>
        <translation>можно безопасно отсоединить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>ejected</source>
        <translation>извлечён</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>unmounted; safe to unplug</source>
        <translation>отключён; можно безопасно отсоединить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>This drive doesn&apos;t report its health to udisks.</source>
        <translation>Этот диск не сообщает udisks о своём состоянии.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>smartctl needs root to read this drive; udisks has no health data for it.</source>
        <translation>smartctl нужны права root, чтобы прочитать этот диск; у udisks нет данных о его состоянии.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>No health data for this drive.</source>
        <translation>Нет данных о состоянии этого диска.</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.driveview</name>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Temperature</source>
        <translation>Температура</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Powered on</source>
        <translation>Наработка</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Bad sectors</source>
        <translation>Плохие секторы</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Wear (of rated life)</source>
        <translation>Износ (от расчётного ресурса)</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Spare blocks left</source>
        <translation>Осталось резервных блоков</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Spare warning level</source>
        <translation>Порог предупреждения о резерве</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Data written</source>
        <translation>Записано данных</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Data read</source>
        <translation>Прочитано данных</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Power cycles</source>
        <translation>Циклы включения</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Unsafe shutdowns</source>
        <translation>Аварийные отключения</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Media errors</source>
        <translation>Ошибки носителя</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Error log entries</source>
        <translation>Записи в журнале ошибок</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Sensors</source>
        <translation>Датчики</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Last self-test</source>
        <translation>Последний самотест</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>passed</source>
        <translation>пройден</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>running</source>
        <translation>выполняется</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>aborted</source>
        <translation>отменён</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>interrupted</source>
        <translation>прерван</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>encrypted, locked</source>
        <translation>зашифрован, заблокирован</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>encrypted · {fs}</source>
        <translation>зашифрован · {fs}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>swap</source>
        <translation>подкачка</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>extended</source>
        <translation>расширенный</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>no file system</source>
        <translation>нет файловой системы</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Health unknown</source>
        <translation>Состояние неизвестно</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Failing</source>
        <translation>Отказывает</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Healthy</source>
        <translation>Исправен</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Health of {drive}</source>
        <translation>Состояние {drive}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>serial {serial}</source>
        <translation>серийный номер {serial}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>firmware {version}</source>
        <translation>прошивка {version}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Reading health data…</source>
        <translation>Чтение данных о состоянии…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Attribute</source>
        <translation>Атрибут</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Value</source>
        <translation>Значение</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Worst</source>
        <translation>Худшее</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Threshold</source>
        <translation>Порог</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Raw</source>
        <translation>Сырое</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Close</source>
        <translation>Закрыть</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Healthy: the drive reports no problems.</source>
        <translation>Исправен: диск не сообщает ни о каких проблемах.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Failing: back up what&apos;s on it now and plan to replace it.</source>
        <translation>Отказывает: сделайте резервную копию данных с него прямо сейчас и запланируйте замену.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Warning from the drive: {warning}</source>
        <translation>Предупреждение от диска: {warning}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Read with smartctl.</source>
        <translation>Прочитано с помощью smartctl.</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>%n hour(s)</source>
        <translation>
            <numerusform>%n час</numerusform>
            <numerusform>%n часа</numerusform>
            <numerusform>%n часов</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>SYSTEM</source>
        <translation>СИСТЕМНЫЙ</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Show the drive&apos;s health report (SMART)</source>
        <translation>Показать отчёт о состоянии диска (SMART)</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Eject</source>
        <translation>Извлечь</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Safely remove</source>
        <translation>Безопасно извлечь</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Unmounts everything on it, then powers it off so it can be unplugged</source>
        <translation>Отключает всё, что на нём смонтировано, и выключает его, чтобы его можно было отсоединить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>No media</source>
        <translation>Нет носителя</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>No partitions or file systems on this drive.</source>
        <translation>На этом диске нет разделов или файловых систем.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>not mounted</source>
        <translation>не подключён</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Open</source>
        <comment>verb</comment>
        <translation>Открыть</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Open in VaultL</source>
        <translation>Открыть в VaultL</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Unmount</source>
        <translation>Отключить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>The system runs from it, so it stays mounted</source>
        <translation>С него работает система, поэтому он остаётся подключённым</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Mount</source>
        <translation>Подключить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>{used} of {total}</source>
        <translation>{used} из {total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Formatting and partitions</source>
        <translation>Форматирование и разделы</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Creating, resizing, formatting and deleting partitions can erase a whole disk, so SystemL leaves them to KDE Partition Manager, which checks every step and asks for your password.</source>
        <translation>Создание, изменение размера, форматирование и удаление разделов может стереть весь диск, поэтому SystemL оставляет это Менеджеру разделов KDE, который проверяет каждый шаг и спрашивает ваш пароль.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>It isn&apos;t installed: {command}</source>
        <translation>Он не установлен: {command}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Open Partition Manager</source>
        <translation>Открыть Менеджер разделов</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>udisks2 isn&apos;t available, so drives are listed read-only (from lsblk): nothing can be mounted or removed from here.</source>
        <translation>udisks2 недоступен, поэтому диски показаны только для чтения (из lsblk): отсюда ничего нельзя подключить или извлечь.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>No drives found.</source>
        <translation>Диски не найдены.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>read {read}   write {write}</source>
        <translation>чтение {read}   запись {write}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>mounted at {folder}</source>
        <translation>подключён в {folder}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Couldn&apos;t start KDE Partition Manager.</source>
        <translation>Не удалось запустить Менеджер разделов KDE.</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.journal</name>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Emergency</source>
        <translation>Авария</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Alert</source>
        <translation>Тревога</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Critical</source>
        <translation>Критично</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Error</source>
        <translation>Ошибка</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Warning</source>
        <translation>Предупреждение</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Notice</source>
        <translation>Уведомление</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Info</source>
        <translation>Информация</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Debug</source>
        <translation>Отладка</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Couldn&apos;t run journalctl: {error}</source>
        <translation>Не удалось запустить journalctl: {error}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>journalctl stopped ({code})</source>
        <translation>journalctl остановился ({code})</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.logview</name>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Time</source>
        <translation>Время</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Level</source>
        <translation>Уровень</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Source</source>
        <translation>Источник</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Message</source>
        <translation>Сообщение</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>All levels</source>
        <translation>Все уровни</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Critical and worse</source>
        <translation>Критичные и хуже</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Errors and worse</source>
        <translation>Ошибки и хуже</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Warnings and worse</source>
        <translation>Предупреждения и хуже</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Notices and worse</source>
        <translation>Уведомления и хуже</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Everything but debug</source>
        <translation>Всё, кроме отладки</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Any time</source>
        <translation>За всё время</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last 15 minutes</source>
        <translation>Последние 15 минут</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last hour</source>
        <translation>Последний час</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last 24 hours</source>
        <translation>Последние 24 часа</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last 7 days</source>
        <translation>Последние 7 дней</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Custom range…</source>
        <translation>Свой период…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Yours</source>
        <translation>Ваши</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>System</source>
        <translation>Система</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Messages from the system and its services</source>
        <translation>Сообщения системы и её служб</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only members of the systemd-journal or adm group can read the system journal. To join: {command}, then log out and back in.</source>
        <translation>Системный журнал могут читать только члены группы systemd-journal или adm. Чтобы вступить: {command}, затем выйдите из сеанса и войдите снова.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Search messages</source>
        <translation>Искать в сообщениях</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Keep reading: new messages appear as they&apos;re written</source>
        <translation>Продолжать чтение: новые сообщения появляются по мере записи</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Follow</source>
        <translation>Следить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Any unit or app</source>
        <translation>Любой юнит или приложение</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last %n entries</source>
        <translation>
            <numerusform>Последняя %n запись</numerusform>
            <numerusform>Последние %n записи</numerusform>
            <numerusform>Последние %n записей</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Lowest level to show</source>
        <translation>Минимальный уровень</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Which boot</source>
        <translation>Какая загрузка</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Time range</source>
        <translation>Период</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only this unit or app</source>
        <translation>Только этот юнит или приложение</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>How many of the newest entries to read</source>
        <translation>Сколько последних записей читать</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>From</source>
        <translation>С</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>to</source>
        <translation>по</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Pick a line to see every field the journal keeps for it.</source>
        <translation>Выберите строку, чтобы увидеть все поля, которые журнал хранит для неё.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy</source>
        <translation>Копировать</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy the selected lines ({key})</source>
        <translation>Копировать выбранные строки ({key})</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Export…</source>
        <translation>Экспорт…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Save the lines shown to a text or JSON file ({key})</source>
        <translation>Сохранить показанные строки в текстовый или JSON-файл ({key})</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Reload</source>
        <translation>Обновить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>This boot</source>
        <translation>Эта загрузка</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Boot of {when}</source>
        <translation>Загрузка {when}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>All boots</source>
        <translation>Все загрузки</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>journalctl: {error}</source>
        <translation>journalctl: {error}</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Reading the journal… %n entries so far</source>
        <translation>
            <numerusform>Чтение журнала… пока %n запись</numerusform>
            <numerusform>Чтение журнала… пока %n записи</numerusform>
            <numerusform>Чтение журнала… пока %n записей</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Following · %n entries</source>
        <translation>
            <numerusform>Слежение · %n запись</numerusform>
            <numerusform>Слежение · %n записи</numerusform>
            <numerusform>Слежение · %n записей</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Nothing matches these filters.</source>
        <translation>Под эти фильтры ничего не подходит.</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>%n entries</source>
        <translation>
            <numerusform>%n запись</numerusform>
            <numerusform>%n записи</numerusform>
            <numerusform>%n записей</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>%n selected</source>
        <translation>
            <numerusform>выбрана %n</numerusform>
            <numerusform>выбрано %n</numerusform>
            <numerusform>выбрано %n</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>%n line(s) copied</source>
        <translation>
            <numerusform>Скопирована %n строка</numerusform>
            <numerusform>Скопировано %n строки</numerusform>
            <numerusform>Скопировано %n строк</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy selected lines</source>
        <translation>Копировать выбранные строки</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy message</source>
        <translation>Копировать сообщение</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy all fields</source>
        <translation>Копировать все поля</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only {unit}</source>
        <translation>Только {unit}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only {app}</source>
        <translation>Только {app}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Every unit and app</source>
        <translation>Все юниты и приложения</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Text (*.txt *.log);;JSON lines (*.jsonl *.json)</source>
        <translation>Текст (*.txt *.log);;Строки JSON (*.jsonl *.json)</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Export log</source>
        <translation>Экспорт журнала</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Saved %n line(s) to {path}</source>
        <translation>
            <numerusform>Сохранена %n строка в {path}</numerusform>
            <numerusform>Сохранено %n строки в {path}</numerusform>
            <numerusform>Сохранено %n строк в {path}</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Couldn&apos;t save the log: {error}</source>
        <translation>Не удалось сохранить журнал: {error}</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.page</name>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Overview</source>
        <translation>Обзор</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Processes</source>
        <translation>Процессы</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Apps &amp; history</source>
        <translation>Приложения и история</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Services</source>
        <translation>Службы</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Startup apps</source>
        <translation>Автозапуск</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Drives</source>
        <translation>Диски</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Logs</source>
        <translation>Журналы</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Alerts</source>
        <translation>Оповещения</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Very high</source>
        <translation>Очень высокий</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>High</source>
        <translation>Высокий</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Normal</source>
        <translation>Обычный</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Low</source>
        <translation>Низкий</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Very low</source>
        <translation>Очень низкий</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>running</source>
        <translation>работает</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>sleeping</source>
        <translation>спит</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>disk-sleep</source>
        <translation>ждёт диск</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>stopped</source>
        <translation>приостановлен</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>tracing-stop</source>
        <translation>остановлен отладчиком</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>zombie</source>
        <translation>зомби</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>dead</source>
        <translation>завершён</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>idle</source>
        <translation>простаивает</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>parked</source>
        <translation>припаркован</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>waking</source>
        <translation>просыпается</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>active</source>
        <translation>активна</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>inactive</source>
        <translation>неактивна</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>failed</source>
        <translation>сбой</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>activating</source>
        <translation>запускается</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>deactivating</source>
        <translation>останавливается</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>reloading</source>
        <translation>перезагружается</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>exited</source>
        <translation>завершена</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>waiting</source>
        <translation>ожидает</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>listening</source>
        <translation>слушает</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>auto-restart</source>
        <translation>автоперезапуск</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>mounted</source>
        <translation>смонтирована</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>plugged</source>
        <translation>подключена</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>enabled</source>
        <translation>включена</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>disabled</source>
        <translation>отключена</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>static</source>
        <translation>статическая</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>indirect</source>
        <translation>косвенная</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>masked</source>
        <translation>замаскирована</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>generated</source>
        <translation>сгенерирована</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>alias</source>
        <translation>псевдоним</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>enabled-runtime</source>
        <translation>включена до перезагрузки</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>linked</source>
        <translation>связана</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Name</source>
        <translation>Имя</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>User</source>
        <translation>Пользователь</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>CPU</source>
        <translation>ЦП</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Memory</source>
        <translation>Память</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Disk</source>
        <translation>Диск</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Threads</source>
        <translation>Потоки</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Priority</source>
        <translation>Приоритет</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Status</source>
        <translation>Состояние</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Search name, command or PID</source>
        <translation>Поиск по имени, команде или PID</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Tree</source>
        <translation>Дерево</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Only mine</source>
        <translation>Только мои</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Kernel threads</source>
        <translation>Потоки ядра</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause</source>
        <translation>Приостановить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit</source>
        <translation>Принудительно завершить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End process</source>
        <translation>Завершить процесс</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Resume</source>
        <translation>Продолжить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{name} · PID {pid} · started {when}</source>
        <translation>{name} · PID {pid} · запущен {when}</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>%n process(es)</source>
        <translation>
            <numerusform>%n процесс</numerusform>
            <numerusform>%n процесса</numerusform>
            <numerusform>%n процессов</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Show only this app</source>
        <translation>Показать только это приложение</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Open its folder</source>
        <translation>Открыть его папку</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit {name}</source>
        <translation>Принудительно завершить {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End {name}</source>
        <translation>Завершить {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause {name}</source>
        <translation>Приостановить {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit {name} (PID {pid})? Unsaved work in it will be lost.</source>
        <translation>Принудительно завершить {name} (PID {pid})? Несохранённые данные в нём будут потеряны.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End {name} (PID {pid})? It gets the chance to save and close.</source>
        <translation>Завершить {name} (PID {pid})? У него будет возможность сохраниться и закрыться.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause {name} (PID {pid})? It freezes until you resume it; if other apps wait on it, they freeze too.</source>
        <translation>Приостановить {name} (PID {pid})? Он замрёт, пока вы его не продолжите; если другие приложения ждут его, они тоже замрут.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>It belongs to another user, so this asks for your password.</source>
        <translation>Он принадлежит другому пользователю, поэтому потребуется ваш пароль.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{name} priority</source>
        <translation>приоритет {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Now</source>
        <translation>Сейчас</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Hour</source>
        <translation>Час</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Day</source>
        <translation>Сутки</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Week</source>
        <translation>Неделя</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MEMORY</source>
        <translation>ПАМЯТЬ</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>App</source>
        <translation>Приложение</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Avg CPU</source>
        <translation>Средняя нагрузка ЦП</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Peak CPU</source>
        <translation>Пик ЦП</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Avg memory</source>
        <translation>Средняя память</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Peak memory</source>
        <translation>Пик памяти</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Minutes</source>
        <translation>Минуты</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Live, summed over every process of each app. Double-click one to see its processes.</source>
        <translation>В реальном времени, суммарно по всем процессам каждого приложения. Дважды щёлкните, чтобы увидеть его процессы.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>History is recorded while SystemL is open (busiest apps, once a minute, kept a week). {h} h {m} min recorded so far.</source>
        <translation>История записывается, пока открыт SystemL (самые загруженные приложения, раз в минуту, хранится неделю). Записано: {h} ч {m} мин.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Nothing recorded yet: history builds up minute by minute while SystemL is open.</source>
        <translation>Пока ничего не записано: история накапливается минута за минутой, пока открыт SystemL.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{app} · CPU</source>
        <translation>{app} · ЦП</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{app} · MEMORY</source>
        <translation>{app} · ПАМЯТЬ</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>System</source>
        <translation>Система</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Yours</source>
        <translation>Ваши</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Search services</source>
        <translation>Поиск служб</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Running only</source>
        <translation>Только работающие</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Failed only</source>
        <translation>Только со сбоем</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Service</source>
        <translation>Служба</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>State</source>
        <translation>Состояние</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Startup</source>
        <translation>Запуск</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Description</source>
        <translation>Описание</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Log</source>
        <translation>Журнал</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start at boot</source>
        <translation>Запускать при загрузке</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Don&apos;t start at boot</source>
        <translation>Не запускать при загрузке</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart</source>
        <translation>Перезапустить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop</source>
        <translation>Остановить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start</source>
        <translation>Запустить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Loading services…</source>
        <translation>Загрузка служб…</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{shown} of %n service(s)</source>
        <translation>
            <numerusform>{shown} из %n службы</numerusform>
            <numerusform>{shown} из %n служб</numerusform>
            <numerusform>{shown} из %n служб</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>%n failed</source>
        <translation>
            <numerusform>%n со сбоем</numerusform>
            <numerusform>%n со сбоем</numerusform>
            <numerusform>%n со сбоем</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{unit} keeps the system running, so it can&apos;t be stopped or restarted from here</source>
        <translation>{unit} поддерживает работу системы, поэтому её нельзя остановить или перезапустить отсюда</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{unit} · system changes ask for your password</source>
        <translation>{unit} · системные изменения требуют пароль</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop {unit}? Whatever depends on it may stop working.</source>
        <translation>Остановить {unit}? Всё, что от неё зависит, может перестать работать.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop starting {unit} at boot? Whatever depends on it may stop working.</source>
        <translation>Больше не запускать {unit} при загрузке? Всё, что от неё зависит, может перестать работать.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart {unit}? Whatever depends on it may stop working for a moment.</source>
        <translation>Перезапустить {unit}? Всё, что от неё зависит, может ненадолго перестать работать.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>NEEDED BY PLASMA</source>
        <translation>НУЖНО PLASMA</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Remove</source>
        <translation>Удалить</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Apps and helpers that start when you log in. Turning one off writes an override in {folder}, the same way Plasma&apos;s settings do; turning it back on removes it.</source>
        <translation>Приложения и помощники, которые запускаются при входе. Отключение записывает переопределение в {folder} — так же, как это делают настройки Plasma; повторное включение его удаляет.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Add app…</source>
        <translation>Добавить приложение…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Nothing starts at login besides Plasma itself.</source>
        <translation>При входе не запускается ничего, кроме самой Plasma.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop {name} from starting at login and move its entry to the Trash?</source>
        <translation>Больше не запускать {name} при входе и переместить его запись в Корзину?</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Add to startup</source>
        <translation>Добавить в автозапуск</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start this app when you log in:</source>
        <translation>Запускать это приложение при входе:</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>added</source>
        <translation>добавлено</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Swap</source>
        <translation>Подкачка</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Failed services</source>
        <translation>Службы со сбоем</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>used</source>
        <translation>занято</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cache</source>
        <translation>кэш</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>read</source>
        <translation>чтение</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>write</source>
        <translation>запись</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Network</source>
        <translation>Сеть</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>down</source>
        <translation>приём</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>up</source>
        <translation>отдача</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Temperature</source>
        <translation>Температура</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Load average</source>
        <translation>Средняя нагрузка</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Cores</source>
        <translation>Ядра</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Busiest right now</source>
        <translation>Самые загруженные сейчас</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Biggest in memory</source>
        <translation>Больше всего памяти</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Quick actions</source>
        <translation>Быстрые действия</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Empty swap into RAM</source>
        <translation>Вернуть подкачку в ОЗУ</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Moves everything in swap back into memory when it fits (asks for your password). Handy after a big game when the desktop feels sluggish.</source>
        <translation>Переносит всё из подкачки обратно в память, если хватает места (потребуется пароль). Полезно после большой игры, когда рабочий стол тормозит.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart Plasma desktop</source>
        <translation>Перезапустить рабочий стол Plasma</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restarts the panel and desktop without logging out. Open apps keep running.</source>
        <translation>Перезапускает панель и рабочий стол без выхода из сеанса. Открытые приложения продолжат работать.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Clear failed services</source>
        <translation>Сбросить сбойные службы</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Forgets your user services&apos; failed state so the count starts fresh.</source>
        <translation>Сбрасывает состояние сбоя ваших пользовательских служб, и счёт начинается заново.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Open OptimizeL</source>
        <translation>Открыть OptimizeL</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Speed tweaks for this PC as on/off switches.</source>
        <translation>Ускоряющие настройки для этого ПК в виде переключателей.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>This PC</source>
        <translation>Этот ПК</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Show its processes</source>
        <translation>Показать его процессы</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>of {total}</source>
        <translation>из {total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>no swap</source>
        <translation>нет подкачки</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{used} of {total}</source>
        <translation>{used} из {total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>5 min {five} · 15 min {fifteen}</source>
        <translation>5 мин {five} · 15 мин {fifteen}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MONITOR</source>
        <translation>МОНИТОРИНГ</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MANAGE</source>
        <translation>УПРАВЛЕНИЕ</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Up {time}
Load {load}</source>
        <translation>Работает {time}
Нагрузка {load}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>done</source>
        <translation>готово</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cancelled</source>
        <translation>отменено</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{what}: {result}</source>
        <translation>{what}: {result}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Couldn&apos;t change {what}: {error}</source>
        <translation>Не удалось изменить {what}: {error}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Empty swap</source>
        <translation>Очистить подкачку</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Move everything in swap back into RAM? This asks for your password and only runs when there&apos;s room.</source>
        <translation>Перенести всё из подкачки обратно в ОЗУ? Потребуется пароль, и это сработает, только если хватает места.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>emptied into RAM</source>
        <translation>перенесено в ОЗУ</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart Plasma</source>
        <translation>Перезапустить Plasma</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart the Plasma desktop and panel? Your open apps keep running.</source>
        <translation>Перезапустить рабочий стол и панель Plasma? Открытые приложения продолжат работать.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>restarted</source>
        <translation>перезапущено</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cleared · %n failed system service(s) left</source>
        <translation>
            <numerusform>сброшено · осталась %n системная служба со сбоем</numerusform>
            <numerusform>сброшено · осталось %n системные службы со сбоем</numerusform>
            <numerusform>сброшено · осталось %n системных служб со сбоем</numerusform>
        </translation>
    </message>
    <message>
        <source>{unit} log</source>
        <translation type="vanished">Журнал {unit}</translation>
    </message>
    <message>
        <source>Disks</source>
        <translation type="vanished">Диски</translation>
    </message>
    <message>
        <source>no file system</source>
        <translation type="vanished">нет файловой системы</translation>
    </message>
    <message>
        <source>not mounted</source>
        <translation type="vanished">не смонтирован</translation>
    </message>
    <message>
        <source>Open</source>
        <translation type="vanished">Открыть</translation>
    </message>
    <message>
        <source>Unmount</source>
        <translation type="vanished">Отмонтировать</translation>
    </message>
    <message>
        <source>read {read}   write {write}</source>
        <translation type="vanished">чтение {read}   запись {write}</translation>
    </message>
    <message>
        <source>system changes ask for your password</source>
        <translation type="vanished">системные изменения требуют пароль</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.probe</name>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>%n core(s)</source>
        <translation>
            <numerusform>%n ядро</numerusform>
            <numerusform>%n ядра</numerusform>
            <numerusform>%n ядер</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>%n thread(s)</source>
        <translation>
            <numerusform>%n поток</numerusform>
            <numerusform>%n потока</numerusform>
            <numerusform>%n потоков</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>System</source>
        <translation>Система</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Kernel</source>
        <translation>Ядро</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Desktop</source>
        <translation>Рабочий стол</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>CPU</source>
        <translation>ЦП</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Memory</source>
        <translation>Память</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>{d} d {h} h {m} min</source>
        <translation>{d} д {h} ч {m} мин</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>{h} h {m} min</source>
        <translation>{h} ч {m} мин</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>{m} min</source>
        <translation>{m} мин</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.system</name>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>the helper failed ({code})</source>
        <translation>помощник завершился с ошибкой ({code})</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>that process can&apos;t be stopped from here</source>
        <translation>этот процесс нельзя остановить отсюда</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>already gone</source>
        <translation>уже завершён</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>{name} keeps your session running; not stopping it</source>
        <translation>{name} поддерживает ваш сеанс; останавливать не будем</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>done</source>
        <translation>готово</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>systemctl {action} failed</source>
        <translation>systemctl {action}: ошибка</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>Plasma needs this to start; leaving it on</source>
        <translation>Это нужно Plasma для запуска; оставляем включённым</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>only your own startup entries can be removed</source>
        <translation>удалять можно только собственные записи автозапуска</translation>
    </message>
    <message>
        <source>Couldn&apos;t read the log.</source>
        <translation type="vanished">Не удалось прочитать журнал.</translation>
    </message>
    <message>
        <source>No log lines yet.</source>
        <translation type="vanished">В журнале пока пусто.</translation>
    </message>
    <message>
        <source>USB drive</source>
        <translation type="vanished">USB-накопитель</translation>
    </message>
    <message>
        <source>Hard drive</source>
        <translation type="vanished">Жёсткий диск</translation>
    </message>
    <message>
        <source>couldn&apos;t unmount</source>
        <translation type="vanished">не удалось отмонтировать</translation>
    </message>
</context>
</TS>
