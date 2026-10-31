<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="zh_CN" sourcelanguage="en">
<context>
    <name>grimoire.spells.systeml.alerts</name>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} uses the most ({size} GB).</source>
        <translation>{app} 占用最多（{size} GB）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>SystemL alerts work</source>
        <translation>SystemL 提醒正常工作</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>This is how memory, temperature, disk and stuck-app alerts will look.</source>
        <translation>内存、温度、磁盘和卡死应用的提醒会是这个样子。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>RAM is {percent}% used ({used} of {total} GB).</source>
        <translation>内存已用 {percent}%（{used}/{total} GB）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>Memory almost full</source>
        <translation>内存快满了</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>CPU is running hot</source>
        <translation>CPU 温度过高</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>CPU temperature is {now}°C (alert at {limit}°C).</source>
        <translation>CPU 温度为 {now}°C（{limit}°C 时提醒）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>GPU is running hot</source>
        <translation>GPU 温度过高</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>GPU temperature is {now}°C (alert at {limit}°C).</source>
        <translation>GPU 温度为 {now}°C（{limit}°C 时提醒）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{mount} is almost full</source>
        <translation>{mount} 快满了</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{mount} has {free} GB free ({percent}%; alert below {limit}).</source>
        <translation>{mount} 剩余 {free} GB（{percent}%；低于 {limit} 时提醒）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} isn&apos;t responding</source>
        <translation>{app} 没有响应</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>An app isn&apos;t responding</source>
        <translation>有应用没有响应</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>It hasn&apos;t responded for %n min. Wait a little, or close it from its window or SystemL&apos;s Processes.</source>
        <translation>
            <numerusform>它已有 %n 分钟没有响应。再等一会儿，或者从它的窗口或 SystemL 的“进程”中关闭它。</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} is stuck</source>
        <translation>{app} 卡住了</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} (PID {pid}) has waited on a disk or device for %n min without progress, often a frozen network share or USB drive.</source>
        <translation>
            <numerusform>{app}（PID {pid}）已等待磁盘或设备 %n 分钟且毫无进展，常见原因是网络共享或 USB 设备卡死。</numerusform>
        </translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.alertview</name>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Memory</source>
        <translation>内存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when RAM use goes above</source>
        <translation>内存占用超过此值时提醒：</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>CPU temperature</source>
        <translation>CPU 温度</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when the CPU gets hotter than</source>
        <translation>CPU 温度高于此值时提醒：</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>GPU temperature</source>
        <translation>GPU 温度</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when the graphics card gets hotter than</source>
        <translation>显卡温度高于此值时提醒：</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Stuck apps</source>
        <translation>卡死的应用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when a window stays &quot;Not Responding&quot; in KWin, or one of your processes hangs on a disk or device with no progress, for</source>
        <translation>当某个窗口在 KWin 中持续“未响应”，或你的某个进程卡在磁盘或设备上毫无进展，持续以下时长时提醒：</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>min</source>
        <translation>分钟</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Test notification sent</source>
        <translation>测试通知已发送</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Couldn&apos;t send a notification: is the notification service running?</source>
        <translation>无法发送通知：通知服务在运行吗？</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Send test notification</source>
        <translation>发送测试通知</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Background alerts</source>
        <translation>后台提醒</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>While a problem lasts, remind again after</source>
        <translation>问题持续时，再次提醒的间隔：</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Alerts</source>
        <translation>提醒</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Disk free space</source>
        <translation>磁盘剩余空间</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Recent alerts</source>
        <translation>最近的提醒</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>When</source>
        <translation>时间</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Alert</source>
        <translation>提醒</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Details</source>
        <translation>详情</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Nothing yet. Alerts show up here (and as notifications) when something crosses a line.</source>
        <translation>暂无。一旦有指标越过阈值，提醒就会显示在这里（也会弹出通知）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>On: checked once a minute, even while SystemL is closed. Each alert notifies once, then waits until it clears or the reminder time passes.</source>
        <translation>已开启：每分钟检查一次，即使 SystemL 已关闭。每项提醒只通知一次，之后等到问题解除或到达再次提醒时间。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Off. Turn on to get notified in the background (adds a small systemd timer that runs once a minute).</source>
        <translation>已关闭。开启后可在后台收到通知（会添加一个每分钟运行一次的小型 systemd 定时器）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>{value} now</source>
        <translation>当前 {value}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>no CPU sensor found, so it stays quiet</source>
        <translation>未找到 CPU 传感器，因此不会提醒</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>no GPU sensor found, so it stays quiet</source>
        <translation>未找到 GPU 传感器，因此不会提醒</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>No disks found.</source>
        <translation>未找到磁盘。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>{device} · {free} free of {total} · warns when free space drops below</source>
        <translation>{device} · 剩余 {free}，共 {total} · 剩余空间低于此值时提醒：</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>on</source>
        <translation>已开启</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>off</source>
        <translation>已关闭</translation>
    </message>
    <message>
        <source>{free} free of {total}</source>
        <translation type="vanished">剩余 {free}，共 {total}</translation>
    </message>
    <message>
        <source>warns when free space drops below</source>
        <translation type="vanished">剩余空间低于此值时提醒：</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.drives</name>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Drive actions need python3-dbus: {command}</source>
        <translation>磁盘操作需要 python3-dbus：{command}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>not allowed (polkit refused)</source>
        <translation>不允许（polkit 拒绝）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>it&apos;s in use: close the files and apps using it, then try again</source>
        <translation>它正在使用中：关闭正在使用它的文件和应用后再试</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>udisks2 isn&apos;t running</source>
        <translation>udisks2 未运行</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>USB drive</source>
        <translation>U 盘</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Hard drive</source>
        <translation>机械硬盘</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Optical drive</source>
        <translation>光驱</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Memory card</source>
        <translation>存储卡</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Virtual disk</source>
        <translation>虚拟磁盘</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>not a udisks device</source>
        <translation>不是 udisks 设备</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>the system runs from it, so it stays mounted</source>
        <translation>系统运行在它上面，所以保持挂载</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>unmounted</source>
        <translation>已卸载</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>the system runs from this drive</source>
        <translation>系统运行在这块磁盘上</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>safe to unplug</source>
        <translation>可以安全拔出</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>ejected</source>
        <translation>已弹出</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>unmounted; safe to unplug</source>
        <translation>已卸载；可以安全拔出</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>This drive doesn&apos;t report its health to udisks.</source>
        <translation>这块磁盘不向 udisks 报告健康状况。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>smartctl needs root to read this drive; udisks has no health data for it.</source>
        <translation>smartctl 需要 root 才能读取这块磁盘；udisks 没有它的健康数据。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>No health data for this drive.</source>
        <translation>这块磁盘没有健康数据。</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.driveview</name>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Temperature</source>
        <translation>温度</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Powered on</source>
        <translation>通电时间</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Bad sectors</source>
        <translation>坏扇区</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Wear (of rated life)</source>
        <translation>磨损（占额定寿命）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Spare blocks left</source>
        <translation>剩余备用块</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Spare warning level</source>
        <translation>备用块警告线</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Data written</source>
        <translation>已写入数据</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Data read</source>
        <translation>已读取数据</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Power cycles</source>
        <translation>通电次数</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Unsafe shutdowns</source>
        <translation>异常断电</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Media errors</source>
        <translation>介质错误</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Error log entries</source>
        <translation>错误日志条目</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Sensors</source>
        <translation>传感器</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Last self-test</source>
        <translation>上次自检</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>passed</source>
        <translation>通过</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>running</source>
        <translation>进行中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>aborted</source>
        <translation>已中止</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>interrupted</source>
        <translation>被中断</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>encrypted, locked</source>
        <translation>已加密，已锁定</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>encrypted · {fs}</source>
        <translation>已加密 · {fs}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>swap</source>
        <translation>交换分区</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>extended</source>
        <translation>扩展分区</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>no file system</source>
        <translation>无文件系统</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Health unknown</source>
        <translation>健康状况未知</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Failing</source>
        <translation>即将损坏</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Healthy</source>
        <translation>健康</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Health of {drive}</source>
        <translation>{drive} 的健康状况</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>serial {serial}</source>
        <translation>序列号 {serial}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>firmware {version}</source>
        <translation>固件 {version}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Reading health data…</source>
        <translation>正在读取健康数据…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Attribute</source>
        <translation>属性</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Value</source>
        <translation>值</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Worst</source>
        <translation>最差</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Threshold</source>
        <translation>阈值</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Raw</source>
        <translation>原始值</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Close</source>
        <translation>关闭</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Healthy: the drive reports no problems.</source>
        <translation>健康：磁盘没有报告任何问题。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Failing: back up what&apos;s on it now and plan to replace it.</source>
        <translation>即将损坏：立即备份上面的数据，并计划更换它。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Warning from the drive: {warning}</source>
        <translation>磁盘发出的警告：{warning}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Read with smartctl.</source>
        <translation>使用 smartctl 读取。</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>%n hour(s)</source>
        <translation>
            <numerusform>%n 小时</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>SYSTEM</source>
        <translation>系统</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Show the drive&apos;s health report (SMART)</source>
        <translation>显示磁盘的健康报告（SMART）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Eject</source>
        <translation>弹出</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Safely remove</source>
        <translation>安全移除</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Unmounts everything on it, then powers it off so it can be unplugged</source>
        <translation>卸载上面的所有内容，然后关闭它的电源，以便拔出</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>No media</source>
        <translation>无介质</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>No partitions or file systems on this drive.</source>
        <translation>这块磁盘上没有分区或文件系统。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>not mounted</source>
        <translation>未挂载</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Open</source>
        <comment>verb</comment>
        <translation>打开</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Open in VaultL</source>
        <translation>在 VaultL 中打开</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Unmount</source>
        <translation>卸载</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>The system runs from it, so it stays mounted</source>
        <translation>系统运行在它上面，所以保持挂载</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Mount</source>
        <translation>挂载</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>{used} of {total}</source>
        <translation>{used} / {total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Formatting and partitions</source>
        <translation>格式化和分区</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Creating, resizing, formatting and deleting partitions can erase a whole disk, so SystemL leaves them to KDE Partition Manager, which checks every step and asks for your password.</source>
        <translation>创建、调整大小、格式化和删除分区可能会清空整块磁盘，所以 SystemL 把这些交给 KDE 分区管理器，它会检查每一步并询问你的密码。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>It isn&apos;t installed: {command}</source>
        <translation>它没有安装：{command}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Open Partition Manager</source>
        <translation>打开分区管理器</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>udisks2 isn&apos;t available, so drives are listed read-only (from lsblk): nothing can be mounted or removed from here.</source>
        <translation>udisks2 不可用，所以磁盘以只读方式列出（来自 lsblk）：无法在这里挂载或移除任何东西。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>No drives found.</source>
        <translation>没有找到磁盘。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>read {read}   write {write}</source>
        <translation>读取 {read}   写入 {write}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>mounted at {folder}</source>
        <translation>已挂载到 {folder}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Couldn&apos;t start KDE Partition Manager.</source>
        <translation>无法启动 KDE 分区管理器。</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.journal</name>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Emergency</source>
        <translation>紧急</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Alert</source>
        <translation>警报</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Critical</source>
        <translation>严重</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Error</source>
        <translation>错误</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Warning</source>
        <translation>警告</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Notice</source>
        <translation>注意</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Info</source>
        <translation>信息</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Debug</source>
        <translation>调试</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Couldn&apos;t run journalctl: {error}</source>
        <translation>无法运行 journalctl：{error}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>journalctl stopped ({code})</source>
        <translation>journalctl 已停止（{code}）</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.logview</name>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Time</source>
        <translation>时间</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Level</source>
        <translation>级别</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Source</source>
        <translation>来源</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Message</source>
        <translation>消息</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>All levels</source>
        <translation>所有级别</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Critical and worse</source>
        <translation>严重及以上</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Errors and worse</source>
        <translation>错误及以上</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Warnings and worse</source>
        <translation>警告及以上</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Notices and worse</source>
        <translation>注意及以上</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Everything but debug</source>
        <translation>除调试外全部</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Any time</source>
        <translation>任何时间</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last 15 minutes</source>
        <translation>最近 15 分钟</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last hour</source>
        <translation>最近 1 小时</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last 24 hours</source>
        <translation>最近 24 小时</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last 7 days</source>
        <translation>最近 7 天</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Custom range…</source>
        <translation>自定义时间段…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Yours</source>
        <translation>你的</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>System</source>
        <translation>系统</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Messages from the system and its services</source>
        <translation>系统及其服务的消息</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only members of the systemd-journal or adm group can read the system journal. To join: {command}, then log out and back in.</source>
        <translation>只有 systemd-journal 或 adm 组的成员才能读取系统日志。加入方法：{command}，然后注销并重新登录。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Search messages</source>
        <translation>搜索消息</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Keep reading: new messages appear as they&apos;re written</source>
        <translation>持续读取：新消息写入时就会出现</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Follow</source>
        <translation>跟随</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Any unit or app</source>
        <translation>任意单元或应用</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last %n entries</source>
        <translation>
            <numerusform>最近 %n 条</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Lowest level to show</source>
        <translation>要显示的最低级别</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Which boot</source>
        <translation>哪次启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Time range</source>
        <translation>时间范围</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only this unit or app</source>
        <translation>仅此单元或应用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>How many of the newest entries to read</source>
        <translation>要读取多少条最新条目</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>From</source>
        <translation>从</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>to</source>
        <translation>到</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Pick a line to see every field the journal keeps for it.</source>
        <translation>选择一行即可查看日志为它保存的所有字段。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy</source>
        <translation>复制</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy the selected lines ({key})</source>
        <translation>复制选中的行（{key}）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Export…</source>
        <translation>导出…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Save the lines shown to a text or JSON file ({key})</source>
        <translation>把显示的行保存为文本或 JSON 文件（{key}）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Reload</source>
        <translation>重新载入</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>This boot</source>
        <translation>本次启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Boot of {when}</source>
        <translation>{when} 的启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>All boots</source>
        <translation>所有启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>journalctl: {error}</source>
        <translation>journalctl：{error}</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Reading the journal… %n entries so far</source>
        <translation>
            <numerusform>正在读取日志… 目前 %n 条</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Following · %n entries</source>
        <translation>
            <numerusform>跟随中 · %n 条</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Nothing matches these filters.</source>
        <translation>没有符合这些筛选条件的内容。</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>%n entries</source>
        <translation>
            <numerusform>%n 条</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>%n selected</source>
        <translation>
            <numerusform>已选 %n 条</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>%n line(s) copied</source>
        <translation>
            <numerusform>已复制 %n 行</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy selected lines</source>
        <translation>复制选中的行</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy message</source>
        <translation>复制消息</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy all fields</source>
        <translation>复制所有字段</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only {unit}</source>
        <translation>仅 {unit}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only {app}</source>
        <translation>仅 {app}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Every unit and app</source>
        <translation>所有单元和应用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Text (*.txt *.log);;JSON lines (*.jsonl *.json)</source>
        <translation>文本 (*.txt *.log);;JSON 行 (*.jsonl *.json)</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Export log</source>
        <translation>导出日志</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Saved %n line(s) to {path}</source>
        <translation>
            <numerusform>已将 %n 行保存到 {path}</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Couldn&apos;t save the log: {error}</source>
        <translation>无法保存日志：{error}</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.page</name>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Overview</source>
        <translation>概览</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Processes</source>
        <translation>进程</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Apps &amp; history</source>
        <translation>应用与历史</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Services</source>
        <translation>服务</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Startup apps</source>
        <translation>开机自启应用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Drives</source>
        <translation>磁盘</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Logs</source>
        <translation>日志</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Alerts</source>
        <translation>提醒</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Very high</source>
        <translation>很高</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>High</source>
        <translation>高</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Normal</source>
        <translation>普通</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Low</source>
        <translation>低</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Very low</source>
        <translation>很低</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>running</source>
        <translation>运行中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>sleeping</source>
        <translation>休眠</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>disk-sleep</source>
        <translation>等待磁盘</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>stopped</source>
        <translation>已暂停</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>tracing-stop</source>
        <translation>跟踪暂停</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>zombie</source>
        <translation>僵尸</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>dead</source>
        <translation>已结束</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>idle</source>
        <translation>空闲</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>parked</source>
        <translation>停放</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>waking</source>
        <translation>唤醒中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>active</source>
        <translation>活动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>inactive</source>
        <translation>未活动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>failed</source>
        <translation>失败</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>activating</source>
        <translation>启动中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>deactivating</source>
        <translation>停止中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>reloading</source>
        <translation>重新加载中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>exited</source>
        <translation>已退出</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>waiting</source>
        <translation>等待中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>listening</source>
        <translation>监听中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>auto-restart</source>
        <translation>自动重启中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>mounted</source>
        <translation>已挂载</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>plugged</source>
        <translation>已插入</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>enabled</source>
        <translation>开机启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>disabled</source>
        <translation>已禁用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>static</source>
        <translation>静态</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>indirect</source>
        <translation>间接</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>masked</source>
        <translation>已屏蔽</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>generated</source>
        <translation>自动生成</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>alias</source>
        <translation>别名</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>enabled-runtime</source>
        <translation>本次启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>linked</source>
        <translation>已链接</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Name</source>
        <translation>名称</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>User</source>
        <translation>用户</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>CPU</source>
        <translation>CPU</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Memory</source>
        <translation>内存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Disk</source>
        <translation>磁盘</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Threads</source>
        <translation>线程</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Priority</source>
        <translation>优先级</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Status</source>
        <translation>状态</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Search name, command or PID</source>
        <translation>搜索名称、命令或 PID</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Tree</source>
        <translation>树状</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Only mine</source>
        <translation>仅我的</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Kernel threads</source>
        <translation>内核线程</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause</source>
        <translation>暂停</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit</source>
        <translation>强制退出</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End process</source>
        <translation>结束进程</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Resume</source>
        <translation>继续</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{name} · PID {pid} · started {when}</source>
        <translation>{name} · PID {pid} · 启动于 {when}</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>%n process(es)</source>
        <translation>
            <numerusform>%n 个进程</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Show only this app</source>
        <translation>只显示这个应用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Open its folder</source>
        <translation>打开所在文件夹</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit {name}</source>
        <translation>强制退出 {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End {name}</source>
        <translation>结束 {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause {name}</source>
        <translation>暂停 {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit {name} (PID {pid})? Unsaved work in it will be lost.</source>
        <translation>强制退出 {name}（PID {pid}）？其中未保存的内容将会丢失。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End {name} (PID {pid})? It gets the chance to save and close.</source>
        <translation>结束 {name}（PID {pid}）？它会有机会保存并关闭。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause {name} (PID {pid})? It freezes until you resume it; if other apps wait on it, they freeze too.</source>
        <translation>暂停 {name}（PID {pid}）？它会冻结直到你继续它；依赖它的其他应用也会一起冻结。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>It belongs to another user, so this asks for your password.</source>
        <translation>它属于其他用户，因此需要输入你的密码。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{name} priority</source>
        <translation>{name} 的优先级</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Now</source>
        <translation>现在</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Hour</source>
        <translation>1 小时</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Day</source>
        <translation>1 天</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Week</source>
        <translation>1 周</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MEMORY</source>
        <translation>内存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>App</source>
        <translation>应用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Avg CPU</source>
        <translation>平均 CPU</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Peak CPU</source>
        <translation>峰值 CPU</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Avg memory</source>
        <translation>平均内存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Peak memory</source>
        <translation>峰值内存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Minutes</source>
        <translation>分钟数</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Live, summed over every process of each app. Double-click one to see its processes.</source>
        <translation>实时数据，按应用汇总其全部进程。双击可查看它的进程。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>History is recorded while SystemL is open (busiest apps, once a minute, kept a week). {h} h {m} min recorded so far.</source>
        <translation>历史记录在 SystemL 打开时进行（每分钟记录最忙的应用，保留一周）。目前已记录 {h} 小时 {m} 分钟。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Nothing recorded yet: history builds up minute by minute while SystemL is open.</source>
        <translation>尚无记录：SystemL 打开期间，历史会一分钟一分钟地积累。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{app} · CPU</source>
        <translation>{app} · CPU</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{app} · MEMORY</source>
        <translation>{app} · 内存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>System</source>
        <translation>系统</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Yours</source>
        <translation>你的</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Search services</source>
        <translation>搜索服务</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Running only</source>
        <translation>仅运行中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Failed only</source>
        <translation>仅失败</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Service</source>
        <translation>服务</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>State</source>
        <translation>状态</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Startup</source>
        <translation>启动方式</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Description</source>
        <translation>描述</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Log</source>
        <translation>日志</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start at boot</source>
        <translation>开机启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Don&apos;t start at boot</source>
        <translation>开机不启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart</source>
        <translation>重启</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop</source>
        <translation>停止</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start</source>
        <translation>启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Loading services…</source>
        <translation>正在加载服务…</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{shown} of %n service(s)</source>
        <translation>
            <numerusform>显示 {shown} 个，共 %n 个服务</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>%n failed</source>
        <translation>
            <numerusform>%n 个失败</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{unit} keeps the system running, so it can&apos;t be stopped or restarted from here</source>
        <translation>{unit} 维持着系统运行，因此不能在这里停止或重启</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{unit} · system changes ask for your password</source>
        <translation>{unit} · 系统级更改需要输入你的密码</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop {unit}? Whatever depends on it may stop working.</source>
        <translation>停止 {unit}？依赖它的程序可能会停止工作。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop starting {unit} at boot? Whatever depends on it may stop working.</source>
        <translation>不再开机启动 {unit}？依赖它的程序可能会停止工作。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart {unit}? Whatever depends on it may stop working for a moment.</source>
        <translation>重启 {unit}？依赖它的程序可能会短暂停止工作。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>NEEDED BY PLASMA</source>
        <translation>PLASMA 必需</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Remove</source>
        <translation>移除</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Apps and helpers that start when you log in. Turning one off writes an override in {folder}, the same way Plasma&apos;s settings do; turning it back on removes it.</source>
        <translation>登录时启动的应用和辅助程序。关闭某项会在 {folder} 中写入一个覆盖文件，和 Plasma 设置的做法相同；重新开启会删除它。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Add app…</source>
        <translation>添加应用…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Nothing starts at login besides Plasma itself.</source>
        <translation>登录时除了 Plasma 本身，没有其他程序启动。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop {name} from starting at login and move its entry to the Trash?</source>
        <translation>不再在登录时启动 {name}，并将其条目移入回收站？</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Add to startup</source>
        <translation>添加到开机自启</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start this app when you log in:</source>
        <translation>登录时启动这个应用：</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>added</source>
        <translation>已添加</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Swap</source>
        <translation>交换空间</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Failed services</source>
        <translation>失败的服务</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>used</source>
        <translation>已用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cache</source>
        <translation>缓存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>read</source>
        <translation>读取</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>write</source>
        <translation>写入</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Network</source>
        <translation>网络</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>down</source>
        <translation>下载</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>up</source>
        <translation>上传</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Temperature</source>
        <translation>温度</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Load average</source>
        <translation>平均负载</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Cores</source>
        <translation>核心</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Busiest right now</source>
        <translation>当前最忙</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Biggest in memory</source>
        <translation>内存占用最大</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Quick actions</source>
        <translation>快捷操作</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Empty swap into RAM</source>
        <translation>把交换空间清回内存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Moves everything in swap back into memory when it fits (asks for your password). Handy after a big game when the desktop feels sluggish.</source>
        <translation>在内存放得下时，把交换空间中的所有内容移回内存（需要输入密码）。玩完大型游戏后桌面变卡时很有用。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart Plasma desktop</source>
        <translation>重启 Plasma 桌面</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restarts the panel and desktop without logging out. Open apps keep running.</source>
        <translation>不注销即可重启面板和桌面。已打开的应用会继续运行。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Clear failed services</source>
        <translation>清除失败的服务</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Forgets your user services&apos; failed state so the count starts fresh.</source>
        <translation>清除你的用户服务的失败状态，让计数重新开始。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Open OptimizeL</source>
        <translation>打开 OptimizeL</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Speed tweaks for this PC as on/off switches.</source>
        <translation>以开关形式提供的本机提速调整。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>This PC</source>
        <translation>本机</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Show its processes</source>
        <translation>显示它的进程</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>of {total}</source>
        <translation>共 {total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>no swap</source>
        <translation>无交换空间</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{used} of {total}</source>
        <translation>{used}/{total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>5 min {five} · 15 min {fifteen}</source>
        <translation>5 分钟 {five} · 15 分钟 {fifteen}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MONITOR</source>
        <translation>监视</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MANAGE</source>
        <translation>管理</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Up {time}
Load {load}</source>
        <translation>已运行 {time}
负载 {load}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>done</source>
        <translation>完成</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cancelled</source>
        <translation>已取消</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{what}: {result}</source>
        <translation>{what}：{result}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Couldn&apos;t change {what}: {error}</source>
        <translation>无法更改 {what}：{error}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Empty swap</source>
        <translation>清空交换空间</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Move everything in swap back into RAM? This asks for your password and only runs when there&apos;s room.</source>
        <translation>把交换空间中的所有内容移回内存？这需要输入你的密码，并且只在内存足够时执行。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>emptied into RAM</source>
        <translation>已移回内存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart Plasma</source>
        <translation>重启 Plasma</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart the Plasma desktop and panel? Your open apps keep running.</source>
        <translation>重启 Plasma 桌面和面板？已打开的应用会继续运行。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>restarted</source>
        <translation>已重启</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cleared · %n failed system service(s) left</source>
        <translation>
            <numerusform>已清除 · 还剩 %n 个失败的系统服务</numerusform>
        </translation>
    </message>
    <message>
        <source>{unit} log</source>
        <translation type="vanished">{unit} 日志</translation>
    </message>
    <message>
        <source>Disks</source>
        <translation type="vanished">磁盘</translation>
    </message>
    <message>
        <source>no file system</source>
        <translation type="vanished">无文件系统</translation>
    </message>
    <message>
        <source>not mounted</source>
        <translation type="vanished">未挂载</translation>
    </message>
    <message>
        <source>Open</source>
        <translation type="vanished">打开</translation>
    </message>
    <message>
        <source>Unmount</source>
        <translation type="vanished">卸载</translation>
    </message>
    <message>
        <source>read {read}   write {write}</source>
        <translation type="vanished">读取 {read}   写入 {write}</translation>
    </message>
    <message>
        <source>system changes ask for your password</source>
        <translation type="vanished">系统级更改需要输入你的密码</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.probe</name>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>%n core(s)</source>
        <translation>
            <numerusform>%n 核</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>%n thread(s)</source>
        <translation>
            <numerusform>%n 线程</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>System</source>
        <translation>系统</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Kernel</source>
        <translation>内核</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Desktop</source>
        <translation>桌面</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>CPU</source>
        <translation>CPU</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Memory</source>
        <translation>内存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>{d} d {h} h {m} min</source>
        <translation>{d} 天 {h} 小时 {m} 分钟</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>{h} h {m} min</source>
        <translation>{h} 小时 {m} 分钟</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>{m} min</source>
        <translation>{m} 分钟</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.system</name>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>the helper failed ({code})</source>
        <translation>辅助程序失败（{code}）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>that process can&apos;t be stopped from here</source>
        <translation>不能在这里停止该进程</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>already gone</source>
        <translation>已经不在了</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>{name} keeps your session running; not stopping it</source>
        <translation>{name} 维持着你的会话运行，不会停止它</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>done</source>
        <translation>完成</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>systemctl {action} failed</source>
        <translation>systemctl {action} 失败</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>Plasma needs this to start; leaving it on</source>
        <translation>Plasma 启动需要它，保持开启</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>only your own startup entries can be removed</source>
        <translation>只能移除你自己的自启条目</translation>
    </message>
    <message>
        <source>Couldn&apos;t read the log.</source>
        <translation type="vanished">无法读取日志。</translation>
    </message>
    <message>
        <source>No log lines yet.</source>
        <translation type="vanished">暂无日志。</translation>
    </message>
    <message>
        <source>USB drive</source>
        <translation type="vanished">USB 驱动器</translation>
    </message>
    <message>
        <source>Hard drive</source>
        <translation type="vanished">机械硬盘</translation>
    </message>
    <message>
        <source>couldn&apos;t unmount</source>
        <translation type="vanished">无法卸载</translation>
    </message>
</context>
</TS>
