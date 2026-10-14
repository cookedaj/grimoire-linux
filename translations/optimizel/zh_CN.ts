<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="zh_CN" sourcelanguage="en">
<context>
    <name>grimoire.spells.optimizel.bench</name>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Boot to desktop</source>
        <translation>启动到桌面</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Firmware (BIOS/UEFI)</source>
        <translation>固件（BIOS/UEFI）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Boot loader</source>
        <translation>引导加载程序</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Kernel</source>
        <translation>内核</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Services to desktop</source>
        <translation>服务到桌面</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>One core (SHA-256)</source>
        <translation>单核（SHA-256）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>All cores (SHA-256)</source>
        <translation>全部核心（SHA-256）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>System call</source>
        <translation>系统调用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Memory copy</source>
        <translation>内存复制</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Random reads, many at once</source>
        <translation>大量并发随机读取</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Sequential write</source>
        <translation>顺序写入</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Sequential read</source>
        <translation>顺序读取</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>4K random read</source>
        <translation>4K 随机读取</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>4K read latency</source>
        <translation>4K 读取延迟</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Wake-up delay, typical</source>
        <translation>唤醒延迟（典型）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Wake-up delay, worst 1%</source>
        <translation>唤醒延迟（最差 1%）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Boot</source>
        <translation>启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>CPU</source>
        <translation>CPU</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Memory</source>
        <translation>内存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Disk</source>
        <translation>磁盘</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/bench.py"/>
        <source>Latency</source>
        <translation>延迟</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.optimizel.benchview</name>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>No boots recorded yet</source>
        <translation>还没有记录任何启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Before and after</source>
        <translation>前后对比</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>About 15 seconds of fixed tests, no password: CPU, system calls, memory, a 512 MB disk test in ~/.cache, and how late the scheduler wakes a task while every core is busy (a stand-in for frame pacing). Run it before you change switches, then again after (after a restart for boot and restart-only tweaks). Close games and big downloads first so runs compare fairly.</source>
        <translation>约 15 秒的固定测试，无需密码：CPU、系统调用、内存、在 ~/.cache 中进行的 512 MB 磁盘测试，以及所有核心都繁忙时调度器唤醒任务的延迟（可近似反映帧节奏）。在改动开关前运行一次，改动后再运行一次（启动类和需重启的优化请在重启后运行）。请先关闭游戏和大型下载，让多次运行的结果可以公平比较。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Use latest as baseline</source>
        <translation>将最新一次设为基准</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Run benchmark</source>
        <translation>运行基准测试</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Boot time, last boots</source>
        <translation>最近几次的启动时间</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Bars stack firmware (darkest), boot loader, kernel and services (white). Recorded once per boot whenever OptimizeL opens.</source>
        <translation>柱形依次叠加固件（最深）、引导加载程序、内核和服务（白色）。每次启动后打开 OptimizeL 时记录一次。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Runs</source>
        <translation>运行记录</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>When</source>
        <translation>时间</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Switches on</source>
        <translation>已开启的开关</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>All cores</source>
        <translation>全部核心</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Syscall</source>
        <translation>系统调用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Disk read</source>
        <translation>磁盘读取</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Wake 99%</source>
        <translation>唤醒 99%</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Boot</source>
        <translation>启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Use selected run as baseline</source>
        <translation>将所选记录设为基准</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Baseline</source>
        <translation>基准</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Baseline  ·  {when}</source>
        <translation>基准  ·  {when}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Latest</source>
        <translation>最新</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Latest  ·  {when}</source>
        <translation>最新  ·  {when}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Change</source>
        <translation>变化</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Boot compares the baseline run&apos;s boot with this boot; restart after changing boot tweaks to see their effect.</source>
        <translation>启动一项比较的是基准记录时的启动与本次启动；更改启动类优化后请重启以查看效果。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Firmware takes {seconds} s before Linux even starts: turning on Fast Boot in your BIOS/UEFI setup is the biggest boot win left (no switch here can change it).</source>
        <translation>在 Linux 启动之前，固件就要花 {seconds} 秒：在 BIOS/UEFI 设置中开启快速启动是剩下最大的启动提速（这里的开关无法改变它）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Slowest units this boot: {list}</source>
        <translation>本次启动最慢的单元：{list}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>{when}  (baseline)</source>
        <translation>{when}  （基准）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>No runs yet: run it once now to get a baseline.</source>
        <translation>还没有运行记录：现在运行一次以获得基准。</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>%n run(s) stored. Baseline: {when}.</source>
        <translation>
            <numerusform>已保存 %n 次运行。基准：{when}。</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Running…</source>
        <translation>正在运行…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Starting…</source>
        <translation>正在开始…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Testing: {step}…  keep the PC idle for a few seconds.</source>
        <translation>正在测试：{step}…  请让电脑空闲几秒钟。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>The benchmark failed: {error}</source>
        <translation>基准测试失败：{error}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Done, but some tests failed: {list}</source>
        <translation>已完成，但部分测试失败：{list}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>Couldn&apos;t save: {error}</source>
        <translation>无法保存：{error}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>{change}  same</source>
        <translation>{change}  持平</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>▲ {change} better</source>
        <translation>▲ 提升 {change}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/benchview.py"/>
        <source>▼ {change} worse</source>
        <translation>▼ 下降 {change}</translation>
    </message>
    <message>
        <source>{change}%  same</source>
        <translation type="vanished">{change}%  持平</translation>
    </message>
    <message>
        <source>▲ {change}% better</source>
        <translation type="vanished">▲ 提升 {change}%</translation>
    </message>
    <message>
        <source>▼ {change}% worse</source>
        <translation type="vanished">▼ 下降 {change}%</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.optimizel.kinds</name>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>Instant</source>
        <translation>立即生效</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>After restart</source>
        <translation>重启后生效</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>After log out</source>
        <translation>注销后生效</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>Your kernel or CPU doesn&apos;t have this setting</source>
        <translation>你的内核或 CPU 没有这项设置</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>Your kernel doesn&apos;t have this setting</source>
        <translation>你的内核没有这项设置</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>No disks found</source>
        <translation>没有找到磁盘</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>Your kernel doesn&apos;t offer {scheduler} for {disk}</source>
        <translation>你的内核没有为 {disk} 提供 {scheduler}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>in use</source>
        <translation>使用中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>not set</source>
        <translation>未设置</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>This PC doesn&apos;t boot with GRUB</source>
        <translation>这台电脑不是用 GRUB 启动的</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>You&apos;ve set {option} yourself on the boot line</source>
        <translation>你已在启动参数中自行设置了 {option}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>Only for NVIDIA graphics</source>
        <translation>仅适用于 NVIDIA 显卡</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>Your NVIDIA driver doesn&apos;t have this option</source>
        <translation>你的 NVIDIA 驱动没有这个选项</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>Not installed here</source>
        <translation>此处未安装</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>none</source>
        <translation>无</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>swap: {list}   swappiness {value}</source>
        <translation>交换空间：{list}   swappiness {value}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>running: {list}</source>
        <translation>运行中：{list}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>no early out-of-memory guard running</source>
        <translation>没有运行提前内存不足保护</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>power limit ?</source>
        <translation>功耗上限 ?</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>power limit {now} W (default {default}, max {max})</source>
        <translation>功耗上限 {now} W（默认 {default}，最大 {max}）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>The driver doesn&apos;t report a power limit</source>
        <translation>驱动没有报告功耗上限</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>Your card&apos;s maximum is its default; nothing to raise</source>
        <translation>你的显卡最大值就是默认值；无可提高</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>renice {value}   in the gamemode group</source>
        <translation>renice {value}   已在 gamemode 组中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>renice {value}   not in the gamemode group</source>
        <translation>renice {value}   不在 gamemode 组中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>GameMode isn&apos;t installed (sudo apt install gamemode)</source>
        <translation>未安装 GameMode（sudo apt install gamemode）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>This GameMode doesn&apos;t allow renicing (no limits.d entry)</source>
        <translation>此 GameMode 不允许调整优先级（缺少 limits.d 条目）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>You have your own gamemode.ini; set renice there</source>
        <translation>你有自己的 gamemode.ini；请在其中设置 renice</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>profile {name}</source>
        <translation>配置 {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>power-profiles-daemon isn&apos;t installed</source>
        <translation>未安装 power-profiles-daemon</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>This PC has no performance profile</source>
        <translation>这台电脑没有性能配置</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>default</source>
        <translation>默认</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>indexing on</source>
        <translation>索引开启</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>indexing off</source>
        <translation>索引关闭</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>Baloo isn&apos;t installed</source>
        <translation>未安装 Baloo</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>driver default (1 GB)</source>
        <translation>驱动默认（1 GB）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>cache limit {size}</source>
        <translation>缓存上限 {size}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>doesn&apos;t start at login</source>
        <translation>登录时不启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>starts at login</source>
        <translation>登录时启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>This is a virtual machine, so it&apos;s needed</source>
        <translation>这是虚拟机，所以需要它</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/kinds.py"/>
        <source>You&apos;ve customized this entry yourself</source>
        <translation>你已自行自定义了这个条目</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.optimizel.page</name>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>All</source>
        <translation>全部</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Safe</source>
        <translation>安全</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Aggressive</source>
        <translation>激进</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>On</source>
        <translation>已开</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Off</source>
        <translation>已关</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Gain: {text}</source>
        <translation>收益：{text}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Can go wrong: {text}</source>
        <translation>可能的问题：{text}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Password</source>
        <translation>需要密码</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Installs a package</source>
        <translation>会安装软件包</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Turning this on installs {package} from Ubuntu&apos;s archive</source>
        <translation>开启后会从 Ubuntu 软件源安装 {package}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Recommended</source>
        <translation>推荐</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Already set</source>
        <translation>已设置</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Not needed</source>
        <translation>无需</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Turn on  ·  {tweak}</source>
        <translation>开启  ·  {tweak}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Turn off  ·  {tweak}</source>
        <translation>关闭  ·  {tweak}</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>%n switch(es).</source>
        <translation>
            <numerusform>%n 个开关。</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>%n of them Aggressive.</source>
        <translation>
            <numerusform>其中 %n 个为激进。</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Apply %n change(s)</source>
        <translation>
            <numerusform>应用 %n 项更改</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Tunes this PC for speed. Every switch shows what it changes and what you gain, stays put through restarts, and turning it off puts back exactly what was there.</source>
        <translation>为这台电脑提速。每个开关都会说明改了什么、能得到什么，重启后依然保留，关闭后会原样恢复。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Rescan</source>
        <translation>重新扫描</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Tweaks</source>
        <translation>优化项</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Benchmark</source>
        <translation>基准测试</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Discard</source>
        <translation>放弃</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Apply changes</source>
        <translation>应用更改</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Recommended left</source>
        <translation>剩余推荐</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Already optimal</source>
        <translation>已是最佳</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Waiting on restart</source>
        <translation>等待重启</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Search tweaks: gpu, boot, swap, latency…</source>
        <translation>搜索优化项：gpu、启动、交换、延迟…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>GROUPS</source>
        <translation>分组</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>No tweak matches.</source>
        <translation>没有匹配的优化项。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Scanning…</source>
        <translation>正在扫描…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>{on} of {total} on</source>
        <translation>已开 {on}/{total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Nothing to change</source>
        <translation>无需更改</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>%n change(s)</source>
        <translation>
            <numerusform>%n 项更改</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>nothing to do</source>
        <translation>无事可做</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Applying… if a password prompt opens, it&apos;s for the system changes.</source>
        <translation>正在应用… 如果弹出密码提示，那是为了系统更改。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>{on} to turn on and {off} to turn off.</source>
        <translation>{on} 项待开启，{off} 项待关闭。</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>%n to turn on.</source>
        <translation>
            <numerusform>%n 项待开启。</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>%n to turn off.</source>
        <translation>
            <numerusform>%n 项待关闭。</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Turned on {on} and turned off {off}.</source>
        <translation>已开启 {on} 项，已关闭 {off} 项。</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Turned on %n.</source>
        <translation>
            <numerusform>已开启 %n 项。</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Turned off %n.</source>
        <translation>
            <numerusform>已关闭 %n 项。</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Nothing changed.</source>
        <translation>没有任何更改。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Restart to finish the ones marked so.</source>
        <translation>重启以完成标有此提示的项。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>System changes were skipped because the password prompt was cancelled.</source>
        <translation>由于取消了密码提示，系统更改已跳过。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Problems: {list}</source>
        <translation>问题：{list}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Couldn&apos;t apply: {error}</source>
        <translation>无法应用：{error}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>now  {value}</source>
        <translation>当前  {value}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>now  {value}   →   back to how it was</source>
        <translation>当前  {value}   →   恢复原样</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>now  {value}   →   {target}</source>
        <translation>当前  {value}   →   {target}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Asks for your password once.</source>
        <translation>只需输入一次密码。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Some finish after a restart.</source>
        <translation>部分需重启后完成。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Some finish after you log out.</source>
        <translation>部分需注销后完成。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/page.py"/>
        <source>Couldn&apos;t read this: {error}</source>
        <translation>无法读取：{error}</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.optimizel.perfmode</name>
    <message>
        <location filename="../../grimoire/spells/optimizel/perfmode.py"/>
        <source>performance power profile</source>
        <translation>性能电源配置</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/perfmode.py"/>
        <source>file indexing paused</source>
        <translation>文件索引已暂停</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/perfmode.py"/>
        <source>split-lock throttling off</source>
        <translation>已关闭 split-lock 降速</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/perfmode.py"/>
        <source>, </source>
        <comment>list separator</comment>
        <translation>、</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.optimizel.profiles</name>
    <message>
        <location filename="../../grimoire/spells/optimizel/profiles.py"/>
        <source>Recommended</source>
        <translation>推荐</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/profiles.py"/>
        <source>Safe tweaks only. Nothing can break; all undo with one click.</source>
        <translation>只含安全优化。不会出问题；一键即可全部撤销。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/profiles.py"/>
        <source>Max performance</source>
        <translation>最高性能</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/profiles.py"/>
        <source>Safe and Aggressive tweaks for speed. Read what each Aggressive one risks.</source>
        <translation>安全和激进的提速优化。请阅读每个激进项的风险。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/profiles.py"/>
        <source>Battery / quiet</source>
        <translation>省电 / 安静</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/profiles.py"/>
        <source>Turns off the tweaks that cost power, heat or fan noise.</source>
        <translation>关闭会增加功耗、发热或风扇噪音的优化。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/profiles.py"/>
        <source>Restore everything</source>
        <translation>全部恢复</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/profiles.py"/>
        <source>Every OptimizeL change off, back to exactly how it was.</source>
        <translation>关闭 OptimizeL 的所有更改，完全恢复原样。</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.optimizel.tweaks</name>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>CPU &amp; power</source>
        <translation>CPU 与电源</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Memory</source>
        <translation>内存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Storage</source>
        <translation>存储</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Boot</source>
        <translation>启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Network</source>
        <translation>网络</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Graphics</source>
        <translation>图形</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Gaming</source>
        <translation>游戏</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Desktop</source>
        <translation>桌面</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Services</source>
        <translation>服务</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Startup apps</source>
        <translation>开机启动应用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Safe</source>
        <translation>安全</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Aggressive</source>
        <translation>激进</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>package cache {size}</source>
        <translation>软件包缓存 {size}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>logs {size}</source>
        <translation>日志 {size}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>stop timeout {time}</source>
        <translation>停止超时 {time}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>mitigations off</source>
        <translation>缓解措施已关闭</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>%n active: {list}</source>
        <translation>
            <numerusform>%n 项生效：{list}</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Your CPU isn&apos;t affected by anything that needs a slow mitigation</source>
        <translation>你的 CPU 不受任何需要缓慢缓解措施的漏洞影响</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>NVMe power-state latency allowed {value} µs (power saving off)</source>
        <translation>NVMe 允许的电源状态延迟 {value} µs（已关闭省电）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>NVMe power-state latency allowed {value} µs</source>
        <translation>NVMe 允许的电源状态延迟 {value} µs</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>update checks at low priority</source>
        <translation>更新检查为低优先级</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>update checks at normal priority</source>
        <translation>更新检查为正常优先级</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Laptops need thermald to stay cool</source>
        <translation>笔记本需要 thermald 来保持散热</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>This PC has more than one GPU, which is what gpu-manager is for</source>
        <translation>这台电脑有不止一块 GPU，而 gpu-manager 正是为此而设</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>systemd-networkd is in use, which this serves</source>
        <translation>正在使用 systemd-networkd，而它为其服务</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>File indexing is off, so there&apos;s nothing to slim down</source>
        <translation>文件索引已关闭，没有可精简的</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Performance power profile</source>
        <translation>性能电源配置</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Tells the CPU to boost sooner and stay at high clocks instead of saving watts (on Intel it sets every core&apos;s energy preference, EPP, to performance). KDE&apos;s battery applet shows the same switch.</source>
        <translation>让 CPU 更早加速并保持高频，而不是省电（在 Intel 上会把每个核心的能耗偏好 EPP 设为 performance）。KDE 的电池小部件里也有同样的开关。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>profile performance</source>
        <translation>配置 performance</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Faster clock ramp-up: snappier apps and fewer frame dips in games; 5 to 15% in short bursts.</source>
        <translation>频率提升更快：应用更跟手，游戏掉帧更少；短时负载下快 5% 到 15%。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Turn off the NMI watchdog</source>
        <translation>关闭 NMI 看门狗</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>A kernel lockup detector that fires a timer interrupt on every core and holds one CPU performance counter per core. Desktops don&apos;t need it.</source>
        <translation>一个内核死锁检测器，会在每个核心上触发定时中断，并在每个核心占用一个 CPU 性能计数器。台式机不需要它。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>One fewer periodic interrupt per core and a free performance counter (profilers can use it).</source>
        <translation>每个核心少一个周期性中断，并空出一个性能计数器（可供性能分析工具使用）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Turn off thermald on a desktop</source>
        <translation>在台式机上关闭 thermald</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>thermald is Intel&apos;s laptop cooling daemon. On a desktop the CPU protects itself in hardware, and thermald can only ever cap power. It also sits on the boot path.</source>
        <translation>thermald 是 Intel 的笔记本散热守护进程。在台式机上，CPU 会在硬件层面自我保护，thermald 只会限制功耗。它还处在启动路径上。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>thermald disabled</source>
        <translation>thermald 已禁用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Takes about 2 s off reaching the desktop here (it&apos;s on the boot critical chain), and nothing software-limits the CPU&apos;s power.</source>
        <translation>进入桌面约快 2 秒（它在启动关键链上），而且不再有软件限制 CPU 功耗。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Turn off CPU security mitigations</source>
        <translation>关闭 CPU 安全缓解措施</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Spectre-class fixes add work on every switch into and out of the kernel. Turning them off gets that time back.</source>
        <translation>Spectre 类修复会在每次进出内核时增加开销。关闭它们可以省回这些时间。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>1 to 5% in system-call-heavy work (compiling, file scans, some games); see the syscall benchmark.</source>
        <translation>在系统调用密集的工作中快 1% 到 5%（编译、文件扫描、部分游戏）；见系统调用基准测试。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Real security cost: malicious code (a web page&apos;s JavaScript, a game mod) could read memory it shouldn&apos;t. Never part of a profile; only use it if you understand that trade.</source>
        <translation>有真实的安全代价：恶意代码（网页的 JavaScript、游戏模组）可能读取不该读的内存。它从不包含在任何方案中；只有理解这种取舍时才使用。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Compressed swap in RAM (zram)</source>
        <translation>内存中的压缩交换（zram）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Adds up to 8 GB of zstd-compressed swap that lives in RAM, so idle tabs and apps get squeezed instead of pushed to disk.</source>
        <translation>在内存中添加最多 8 GB 的 zstd 压缩交换空间，闲置的标签页和应用会被压缩，而不是被挤到磁盘上。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>zram up to 8 GB, swappiness 180</source>
        <translation>zram 最多 8 GB，swappiness 180</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Roughly 3x more room before anything touches the disk; the desktop stays smooth when RAM fills.</source>
        <translation>在动用磁盘之前大约多出 3 倍空间；内存吃紧时桌面依然流畅。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Stay responsive when RAM runs out</source>
        <translation>内存耗尽时保持响应</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>earlyoom closes the single biggest app when memory and swap are almost gone, instead of the whole desktop freezing for minutes.</source>
        <translation>当内存和交换空间几乎用尽时，earlyoom 会关闭占用最大的那个应用，而不是让整个桌面卡死好几分钟。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>earlyoom running</source>
        <translation>earlyoom 运行中</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Seconds instead of minutes to recover from running out of memory.</source>
        <translation>内存耗尽后几秒钟就能恢复，而不是几分钟。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Never evict what you just used</source>
        <translation>不清出刚用过的内容</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Multi-gen LRU&apos;s thrashing guard: pages used in the last second can&apos;t be pushed out. If that can&apos;t be kept, the out-of-memory killer acts instead of the system crawling.</source>
        <translation>多代 LRU 的抖动保护：过去一秒内用过的页面不会被换出。如果无法保证，就由内存不足终结器出手，而不是让系统慢如蜗牛。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>No multi-second freezes under memory pressure (the kernel docs suggest 1000 ms for desktops).</source>
        <translation>内存压力下不再有长达数秒的卡顿（内核文档建议桌面使用 1000 ms）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Keep folder info cached</source>
        <translation>保持文件夹信息缓存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Holds directory and file metadata in RAM longer, so file browsing, searches and game launchers that scan many files stay fast.</source>
        <translation>把目录和文件元数据在内存中保留更久，让文件浏览、搜索和需要扫描大量文件的游戏启动器保持快速。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Faster repeat folder scans; costs a few hundred MB at most, cheap with 16 GB or more.</source>
        <translation>重复扫描文件夹更快；最多占用几百 MB，在 16 GB 以上内存时很划算。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Smoother big file copies</source>
        <translation>更顺畅的大文件复制</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>With lots of RAM the kernel lets gigabytes of unwritten data pile up, then stalls everything to flush it. This starts writing at 128 MB and caps it at 256 MB.</source>
        <translation>内存较大时，内核会让数 GB 未写入的数据堆积起来，然后卡住一切去刷写。此项在 128 MB 时开始写入，上限为 256 MB。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>write-back at 128 / 256 MB</source>
        <translation>回写阈值 128 / 256 MB</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>No long freeze at the end of a big copy or game install; copy speed itself is unchanged.</source>
        <translation>大文件复制或游戏安装结束时不再长时间卡住；复制速度本身不变。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Fewer memory-housekeeping stalls</source>
        <translation>更少的内存整理卡顿</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Stops the kernel from defragmenting RAM in the background and from boosting reclaim after every fragmentation event. Both can cause latency spikes.</source>
        <translation>阻止内核在后台整理内存碎片，以及在每次碎片事件后加大回收力度。两者都可能导致延迟尖峰。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Removes a source of random millisecond stalls (the kernel docs warn of them); plenty of RAM means it isn&apos;t needed.</source>
        <translation>去掉一个随机毫秒级卡顿的来源（内核文档对此有警告）；内存充足时不需要它。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Huge pages for every app</source>
        <translation>为所有应用启用大页</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Lets every app use 2 MB memory pages instead of 4 KB ones, with defragmentation done in the background only, so page faults never stall on it.</source>
        <translation>让每个应用使用 2 MB 而不是 4 KB 的内存页，碎片整理只在后台进行，缺页时不会因此卡住。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Fewer TLB misses: 2 to 10% in memory-heavy games, emulators and compilers.</source>
        <translation>更少的 TLB 未命中：内存密集的游戏、模拟器和编译器快 2% 到 10%。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Apps can use noticeably more RAM (a 2 MB page for a little data); max_ptes_none 409 limits that. A few databases (Redis, MongoDB) say to keep huge pages off.</source>
        <translation>应用可能明显多占内存（一点点数据也占 2 MB 页）；max_ptes_none 409 会加以限制。少数数据库（Redis、MongoDB）建议关闭大页。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Right I/O scheduler for each disk</source>
        <translation>为每块磁盘选对 I/O 调度器</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>NVMe drives are fastest with no scheduler at all, SATA SSDs with mq-deadline, hard drives with BFQ (keeps the desktop responsive during big copies). A udev rule picks it per disk, also for new disks.</source>
        <translation>NVMe 硬盘不用调度器最快，SATA SSD 用 mq-deadline，机械硬盘用 BFQ（大文件复制时桌面依然灵敏）。由 udev 规则按磁盘选择，新磁盘也适用。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>per disk type</source>
        <translation>按磁盘类型</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>NVMe: lowest overhead per I/O. Hard drives: no desktop freezes while copying.</source>
        <translation>NVMe：每次 I/O 开销最低。机械硬盘：复制时桌面不卡。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Bigger read-ahead for loading</source>
        <translation>更大的预读以加快加载</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Reads 1 MB ahead (4 MB on hard drives) instead of 128 KB when a program reads a file in order, so game assets, videos and big files stream in larger chunks.</source>
        <translation>程序顺序读取文件时预读 1 MB（机械硬盘 4 MB），而不是 128 KB，让游戏资源、视频和大文件以更大的块读入。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>1 MB (SSD) / 4 MB (HDD)</source>
        <translation>1 MB（SSD）/ 4 MB（HDD）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Faster sequential loads when a program reads with small buffers; see the disk benchmark. Little effect on random access.</source>
        <translation>程序用小缓冲区读取时顺序加载更快；见磁盘基准测试。对随机访问影响不大。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Keep the NVMe drive awake</source>
        <translation>让 NVMe 硬盘保持唤醒</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Stops the drive from dropping into deep power-saving states between bursts, which some drives take milliseconds to wake from.</source>
        <translation>阻止硬盘在两次读写之间进入深度省电状态，有些硬盘从中唤醒需要数毫秒。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>power saving off</source>
        <translation>省电已关闭</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>No NVMe drive</source>
        <translation>没有 NVMe 硬盘</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Lower first-read latency after idle (fewer hitches when a game streams in a new area).</source>
        <translation>空闲后的首次读取延迟更低（游戏加载新区域时卡顿更少）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>The drive idles 1 to 2 W higher and runs warmer; on a laptop that costs battery.</source>
        <translation>硬盘空闲功耗高 1 到 2 W，温度也更高；在笔记本上会耗电。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Don&apos;t hoard downloaded packages</source>
        <translation>不囤积已下载的软件包</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Deletes installer .deb files once updates are installed (apt downloads them again if ever needed).</source>
        <translation>更新安装后删除 .deb 安装文件（需要时 apt 会重新下载）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>cache cleared after installs</source>
        <translation>安装后清空缓存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Frees the package cache now and keeps it empty (often hundreds of MB to GBs).</source>
        <translation>立即释放软件包缓存并保持为空（通常有几百 MB 到数 GB）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Cap system logs at 200 MB</source>
        <translation>将系统日志限制在 200 MB</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Keeps the system journal small, so log writes and log loading stay light.</source>
        <translation>让系统日志保持小巧，写入和加载日志都很轻松。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>journal max 200 MB</source>
        <translation>日志上限 200 MB</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Up to 4 GB of disk back, and faster journal searches.</source>
        <translation>最多腾出 4 GB 磁盘空间，日志搜索也更快。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Reach the login screen sooner</source>
        <translation>更快到达登录界面</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Stops boot from waiting for the network to be fully up. Wi-Fi and Ethernet still connect right after.</source>
        <translation>启动时不再等待网络完全就绪。Wi-Fi 和有线网络随后照常连接。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>wait-online disabled</source>
        <translation>wait-online 已禁用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Often 5 to 10 s off boot on machines where something waits for the network.</source>
        <translation>在有服务等待网络的机器上，启动通常快 5 到 10 秒。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Skip Ubuntu&apos;s GPU switcher check</source>
        <translation>跳过 Ubuntu 的显卡切换检查</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>gpu-manager sorts out laptops with two GPUs before the login screen starts. With a single graphics card it finds nothing to do, every boot.</source>
        <translation>gpu-manager 会在登录界面启动前处理双显卡笔记本。只有一块显卡时，它每次启动都无事可做。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>gpu-manager disabled</source>
        <translation>gpu-manager 已禁用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>About 0.4 s less before the login screen (it runs right before it).</source>
        <translation>登录界面出现前约快 0.4 秒（它就在登录界面之前运行）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>If you later add a second GPU, turn this back off.</source>
        <translation>如果以后加装第二块 GPU，请把这一项关掉。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Don&apos;t wait 90 s on stuck apps at shutdown</source>
        <translation>关机时不为卡住的应用等 90 秒</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>When a service or app hangs while shutting down, systemd waits 90 s before killing it (&quot;A stop job is running...&quot;). This makes it 15 s.</source>
        <translation>关机时如果有服务或应用卡住，systemd 会等 90 秒才结束它（&quot;A stop job is running...&quot;）。此项改为 15 秒。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>stop timeout 15 s</source>
        <translation>停止超时 15 秒</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Up to 75 s off a stuck shutdown or restart; no change when nothing hangs.</source>
        <translation>卡住的关机或重启最多快 75 秒；没有卡住时无变化。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Background jobs yield to you</source>
        <translation>后台任务给你让路</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Update checks, firmware checks, man page indexing, log rotation and disk scrubs run at the lowest CPU (and on SATA, disk) priority.</source>
        <translation>更新检查、固件检查、手册页索引、日志轮转和磁盘校验以最低的 CPU（在 SATA 上还有磁盘）优先级运行。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>nice 19, low CPU weight</source>
        <translation>nice 19，低 CPU 权重</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>They never cause stutter while you play or work; they just finish a bit later.</source>
        <translation>它们不会在你游戏或工作时造成卡顿，只是会晚一点完成。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>BBR congestion control</source>
        <translation>BBR 拥塞控制</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Google&apos;s BBR keeps uploads fast and latency low when the connection is busy (streaming, uploads, game downloads), paired with the fair-queue scheduler.</source>
        <translation>Google 的 BBR 配合公平队列调度器，在连接繁忙时（直播、上传、游戏下载）保持上传快速、延迟低。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Lower ping while the line is busy (no bufferbloat from your side) and faster uploads on lossy Wi-Fi.</source>
        <translation>线路繁忙时 ping 更低（你这一端不再有缓冲膨胀），在丢包的 Wi-Fi 上上传更快。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Room for fast connections</source>
        <translation>为高速连接留足空间</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Lets one upload use a 32 MB window instead of 4 MB, and keeps a connection&apos;s speed after it sits idle (no slow restart between bursts).</source>
        <translation>让单个上传使用 32 MB 而不是 4 MB 的窗口，并在连接空闲后保持速度（两次传输之间不再慢启动）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>32 MB buffers, no idle slow-start</source>
        <translation>32 MB 缓冲区，空闲后不慢启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>A 4 MB window caps one upload at about 80 MB/s to a server 50 ms away; 32 MB lifts that past 1 Gb/s. Matters on gigabit lines.</source>
        <translation>4 MB 窗口会把到 50 ms 外服务器的单个上传限制在约 80 MB/s；32 MB 可突破 1 Gb/s。对千兆线路有意义。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Bigger NVIDIA shader cache</source>
        <translation>更大的 NVIDIA 着色器缓存</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Raises the driver&apos;s shader cache from 1 GB to 10 GB and stops it pruning, so games stop recompiling shaders (the stutter you get in new areas).</source>
        <translation>把驱动的着色器缓存从 1 GB 提高到 10 GB 并停止清理，游戏不再重复编译着色器（就是进入新区域时的卡顿）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>10 GB, no cleanup</source>
        <translation>10 GB，不清理</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>No repeat shader-compile stutter after you&apos;ve played a game once.</source>
        <translation>游戏玩过一次后，不再反复出现着色器编译卡顿。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>GPU power limit at its maximum</source>
        <translation>GPU 功耗上限调到最大</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Raises the graphics card&apos;s power limit from its default to the most the card&apos;s firmware allows, re-applied at every boot.</source>
        <translation>把显卡的功耗上限从默认值提高到固件允许的最大值，每次启动都会重新应用。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>max power limit</source>
        <translation>最大功耗上限</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>1 to 3% in GPU-bound games when the card hits its power limit (watch it in SystemL).</source>
        <translation>显卡触及功耗上限时，GPU 受限的游戏快 1% 到 3%（可在 SystemL 中观察）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>More heat, fan noise and power draw. It stays within NVIDIA&apos;s allowed range, so no damage, but a weak power supply could shut the PC off under full load.</source>
        <translation>发热、风扇噪音和功耗都会增加。它不会超出 NVIDIA 允许的范围，因此不会损坏硬件，但电源较弱时满载可能导致电脑断电。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Skip zeroing GPU system memory</source>
        <translation>跳过 GPU 系统内存清零</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>The NVIDIA driver clears every block of system RAM it hands to a program. Turning that off makes allocations (loading screens, alt-tab, video) cheaper.</source>
        <translation>NVIDIA 驱动会把交给程序的每块系统内存清零。关闭后分配内存（加载画面、alt-tab、视频）的开销更低。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Small: less CPU time on GPU allocations, so loading and alt-tab hitches shrink. CachyOS ships this by default.</source>
        <translation>收益较小：GPU 分配占用的 CPU 时间更少，加载和 alt-tab 的卡顿减轻。CachyOS 默认就这样设置。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>A program could see leftover data from memory another program used before. Low risk on a single-user PC, but it is a security trade.</source>
        <translation>程序可能看到其他程序先前用过的内存中的残留数据。在单用户电脑上风险较低，但这是安全上的取舍。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Don&apos;t throttle split-lock games</source>
        <translation>不对 split-lock 游戏降速</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Some Windows games (via Proton) trip the kernel&apos;s split-lock trap, which slows them down on purpose. Valve turns this off on the Steam Deck.</source>
        <translation>有些 Windows 游戏（通过 Proton）会触发内核的 split-lock 陷阱，内核会故意让它们变慢。Valve 在 Steam Deck 上关闭了这一机制。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Removes 10 ms pauses per hit in the affected games (a few go from stuttering to smooth).</source>
        <translation>在受影响的游戏中，每次触发都不再暂停 10 ms（有些游戏会从卡顿变得流畅）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Enough memory maps for big games</source>
        <translation>为大型游戏提供足够的内存映射</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Some games (and Proton/DXVK) create hundreds of thousands of memory mappings and crash at the old 65530 limit.</source>
        <translation>有些游戏（以及 Proton/DXVK）会创建数十万个内存映射，在旧的 65530 上限处崩溃。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Fixes crashes and hitches in games like Hogwarts Legacy, Star Citizen and CS2.</source>
        <translation>修复《霍格沃茨之遗》、《星际公民》和 CS2 等游戏中的崩溃和卡顿。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Let GameMode boost games</source>
        <translation>让 GameMode 为游戏加速</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Games started with gamemoderun %command% get a higher CPU and I/O priority. That needs a gamemode group with you in it (Ubuntu&apos;s package doesn&apos;t make one) and a gamemode.ini that asks for it.</source>
        <translation>用 gamemoderun %command% 启动的游戏会获得更高的 CPU 和 I/O 优先级。这需要一个包含你的 gamemode 组（Ubuntu 的软件包不会创建）以及一个请求该功能的 gamemode.ini。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Games win the CPU against browsers, launchers and background updates: fewer stutters when something else is busy.</source>
        <translation>游戏在 CPU 上优先于浏览器、启动器和后台更新：其他程序繁忙时卡顿更少。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Snappier animations</source>
        <translation>更利落的动画</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Plays window, menu and desktop animations twice as fast, so everything feels more immediate.</source>
        <translation>窗口、菜单和桌面动画以两倍速度播放，一切都更即时。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>animation speed 2x</source>
        <translation>动画速度 2 倍</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Half the wait on every window open, close and menu.</source>
        <translation>每次打开、关闭窗口和菜单的等待时间减半。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Allow tearing in fullscreen games</source>
        <translation>允许全屏游戏画面撕裂</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Lets KWin show a fullscreen game&apos;s frame the moment it&apos;s ready when the game asks for it (vsync off), instead of waiting for the next refresh.</source>
        <translation>当全屏游戏请求时（关闭垂直同步），让 KWin 在帧就绪时立刻显示，而不是等待下一次刷新。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Up to one refresh (4 ms at 240 Hz) less input lag in games with vsync off.</source>
        <translation>在关闭垂直同步的游戏中，输入延迟最多减少一次刷新（240 Hz 下为 4 ms）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Turn off file indexing</source>
        <translation>关闭文件索引</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Baloo reads every file to build a search index, which costs disk and CPU time. Name search in KRunner and VaultL still works.</source>
        <translation>Baloo 会读取每个文件来建立搜索索引，耗费磁盘和 CPU 时间。KRunner 和 VaultL 中的按名称搜索仍然可用。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>indexing off</source>
        <translation>索引关闭</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>No background disk and CPU load from indexing (heavy after big downloads).</source>
        <translation>不再有索引带来的后台磁盘和 CPU 负载（大型下载之后尤其明显）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Index names only, not file contents</source>
        <translation>只索引文件名，不索引内容</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>If you keep Baloo on, this stops it reading inside every document; searching by name still works.</source>
        <translation>如果保留 Baloo，此项会阻止它读取每个文档的内容；按名称搜索仍然可用。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Most of Baloo&apos;s CPU and disk cost goes away while name search keeps working.</source>
        <translation>Baloo 的大部分 CPU 和磁盘开销都会消失，按名称搜索照常可用。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Start each login fresh</source>
        <translation>每次登录都全新开始</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Logs in to an empty desktop instead of reopening the apps from last time.</source>
        <translation>登录到空桌面，而不是重新打开上次的应用。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>empty session</source>
        <translation>空会话</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Faster login: no apps relaunching at once.</source>
        <translation>登录更快：不会一下子重新启动一堆应用。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Turn off iSCSI network disks</source>
        <translation>关闭 iSCSI 网络磁盘</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Server-style network storage. It also makes boot wait for the network. Nothing on a home PC uses it.</source>
        <translation>服务器式的网络存储。它还会让启动等待网络。家用电脑上没有东西用它。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>iscsi disabled</source>
        <translation>iscsi 已禁用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Less boot work and no boot wait for the network.</source>
        <translation>启动工作更少，也不再等待网络。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Stop auto-adding network printers</source>
        <translation>停止自动添加网络打印机</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>cups-browsed constantly scans the network for printers to add. Printers you&apos;ve set up keep working.</source>
        <translation>cups-browsed 会不停扫描网络来添加打印机。你已设置好的打印机照常可用。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>cups-browsed disabled</source>
        <translation>cups-browsed 已禁用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>One less always-running daemon and less network chatter.</source>
        <translation>少一个常驻守护进程，网络上的杂讯也更少。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Log once, not twice</source>
        <translation>日志只写一次，不写两次</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Ubuntu writes every log message twice: to the systemd journal and again to /var/log/syslog. journalctl (and SystemL) keep everything.</source>
        <translation>Ubuntu 会把每条日志写两次：写入 systemd 日志，再写入 /var/log/syslog。journalctl（以及 SystemL）会保留全部内容。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>rsyslog disabled</source>
        <translation>rsyslog 已禁用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Half the log writes to disk and one less daemon.</source>
        <translation>日志写盘减半，并少一个守护进程。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>/var/log/syslog stops growing; use journalctl to read logs.</source>
        <translation>/var/log/syslog 不再增长；请用 journalctl 查看日志。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Unused network event daemon</source>
        <translation>未使用的网络事件守护进程</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>networkd-dispatcher only reacts to systemd-networkd, which this PC doesn&apos;t use (NetworkManager runs the network).</source>
        <translation>networkd-dispatcher 只响应 systemd-networkd，而这台电脑不使用它（网络由 NetworkManager 管理）。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>networkd-dispatcher disabled</source>
        <translation>networkd-dispatcher 已禁用</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>About 0.3 s of boot work and a ~20 MB Python process gone.</source>
        <translation>省掉约 0.3 秒启动工作和一个约 20 MB 的 Python 进程。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Discover update notifier</source>
        <translation>Discover 更新通知器</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Checks for updates in the background all session. Security updates still install automatically; open Discover when you want app updates.</source>
        <translation>在整个会话中于后台检查更新。安全更新仍会自动安装；需要更新应用时打开 Discover 即可。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>doesn&apos;t start</source>
        <translation>不启动</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>About 100 MB of RAM and periodic package refreshes gone.</source>
        <translation>省掉约 100 MB 内存和定期的软件包刷新。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Virtual machine guest agent</source>
        <translation>虚拟机客户机代理</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>spice-vdagent only does something inside a virtual machine. This PC is real hardware.</source>
        <translation>spice-vdagent 只在虚拟机里才有用。这台电脑是真实硬件。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>One less process at login.</source>
        <translation>登录时少一个进程。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Location agent</source>
        <translation>位置代理</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Shares your location with apps that ask. Unneeded on a desktop unless an app uses it.</source>
        <translation>向请求的应用共享你的位置。除非有应用使用，台式机上不需要它。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Kup backup daemon</source>
        <translation>Kup 备份守护进程</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Background backup service. Leave it on if you use Kup backups.</source>
        <translation>后台备份服务。如果你使用 Kup 备份，请保持开启。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>One less daemon and no surprise backup I/O.</source>
        <translation>少一个守护进程，也不会突然出现备份读写。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>NVIDIA settings loader</source>
        <translation>NVIDIA 设置加载器</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Re-applies X11 settings from nvidia-settings at login. On Wayland it does nothing.</source>
        <translation>登录时重新应用 nvidia-settings 的 X11 设置。在 Wayland 上它什么都不做。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>A slightly quicker login.</source>
        <translation>登录稍快一些。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>KDE Connect</source>
        <translation>KDE Connect</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Phone integration (notifications, file sharing). Leave it on if you pair your phone.</source>
        <translation>手机集成（通知、文件共享）。如果你配对了手机，请保持开启。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>About 40 MB of RAM and its network discovery gone.</source>
        <translation>省掉约 40 MB 内存及其网络发现。</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>{driver} runs in active mode: the CPU picks its own clocks (the power profile sets its energy preference)</source>
        <translation>{driver} 以主动模式运行：CPU 自行选择频率（电源配置设定其能耗偏好）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Turbo boost is on</source>
        <translation>睿频已开启</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Autogroup scheduling keeps the desktop responsive under load</source>
        <translation>自动分组调度让桌面在负载下保持灵敏</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>zswap is off, so swap isn&apos;t compressed twice on top of zram</source>
        <translation>zswap 已关闭，因此交换不会在 zram 之上被压缩两次</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Multi-gen LRU picks what to evict from RAM smartly</source>
        <translation>多代 LRU 能聪明地挑选要从内存中清出的内容</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Huge pages for apps that ask for them (no random stalls)</source>
        <translation>为请求的应用提供大页（不会随机卡顿）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>{disk} uses the &quot;none&quot; I/O scheduler, the fastest for NVMe</source>
        <translation>{disk} 使用 &quot;none&quot; I/O 调度器，这对 NVMe 最快</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Weekly TRIM keeps the SSD fast</source>
        <translation>每周 TRIM 让 SSD 保持快速</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Boot menu is skipped (no countdown)</source>
        <translation>跳过启动菜单（无倒计时）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Boot doesn&apos;t wait for the network</source>
        <translation>启动时不等待网络</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>TCP Fast Open is on</source>
        <translation>TCP Fast Open 已开启</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Downloads can already use a big receive window</source>
        <translation>下载已经可以使用大的接收窗口</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>NVIDIA keeps video memory across suspend (no broken apps after sleep)</source>
        <translation>NVIDIA 在挂起期间保留显存（睡眠后应用不会出错）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>The NVIDIA driver uses PAT memory types (its default since 515)</source>
        <translation>NVIDIA 驱动使用 PAT 内存类型（自 515 版起为默认）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Resizable BAR is on ({size} MiB of video memory visible to the CPU)</source>
        <translation>Resizable BAR 已开启（CPU 可见 {size} MiB 显存）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>nvidia-drm modesetting is on (needed for Wayland)</source>
        <translation>nvidia-drm 模式设置已开启（Wayland 需要）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Persistence mode isn&apos;t needed: with a display attached the driver stays loaded</source>
        <translation>不需要持久模式：接着显示器时驱动会保持加载</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>ntsync is loaded: Wine and Proton builds that support it sync game threads in the kernel (faster)</source>
        <translation>ntsync 已加载：支持它的 Wine 和 Proton 版本会在内核中同步游戏线程（更快）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>GameMode is installed (launch games with gamemoderun %command%)</source>
        <translation>已安装 GameMode（用 gamemoderun %command% 启动游戏）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Proton turns on NVAPI (DLSS, Reflex) by itself on NVIDIA; no variable needed</source>
        <translation>Proton 在 NVIDIA 上会自动开启 NVAPI（DLSS、Reflex）；无需设置变量</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>KWin draws frames at real-time priority</source>
        <translation>KWin 以实时优先级绘制帧</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Restart to finish</source>
        <translation>重启以完成</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Log out to finish</source>
        <translation>注销以完成</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>helper failed ({code})</source>
        <translation>辅助程序失败（{code}）</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>You cancelled the password prompt</source>
        <translation>你取消了密码提示</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>System changes: {error}</source>
        <translation>系统更改：{error}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/optimizel/tweaks.py"/>
        <source>Couldn&apos;t save OptimizeL&apos;s state: {error}</source>
        <translation>无法保存 OptimizeL 的状态：{error}</translation>
    </message>
</context>
</TS>
