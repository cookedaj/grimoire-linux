<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="es" sourcelanguage="en">
<context>
    <name>grimoire.spells.systeml.alerts</name>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} uses the most ({size} GB).</source>
        <translation>{app} es lo que más usa ({size} GB).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>SystemL alerts work</source>
        <translation>Las alertas de SystemL funcionan</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>This is how memory, temperature, disk and stuck-app alerts will look.</source>
        <translation>Así se verán las alertas de memoria, temperatura, disco y apps bloqueadas.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>RAM is {percent}% used ({used} of {total} GB).</source>
        <translation>La RAM está al {percent}% ({used} de {total} GB).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>Memory almost full</source>
        <translation>Memoria casi llena</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>CPU is running hot</source>
        <translation>La CPU está muy caliente</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>CPU temperature is {now}°C (alert at {limit}°C).</source>
        <translation>La temperatura de la CPU es {now}°C (alerta a {limit}°C).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>GPU is running hot</source>
        <translation>La GPU está muy caliente</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>GPU temperature is {now}°C (alert at {limit}°C).</source>
        <translation>La temperatura de la GPU es {now}°C (alerta a {limit}°C).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{mount} is almost full</source>
        <translation>{mount} está casi lleno</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{mount} has {free} GB free ({percent}%; alert below {limit}).</source>
        <translation>{mount} tiene {free} GB libres ({percent}%; alerta por debajo de {limit}).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} isn&apos;t responding</source>
        <translation>{app} no responde</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>An app isn&apos;t responding</source>
        <translation>Una app no responde</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>It hasn&apos;t responded for %n min. Wait a little, or close it from its window or SystemL&apos;s Processes.</source>
        <translation>
            <numerusform>Lleva %n min sin responder. Espera un poco o ciérrala desde su ventana o desde Procesos de SystemL.</numerusform>
            <numerusform>Lleva %n min sin responder. Espera un poco o ciérrala desde su ventana o desde Procesos de SystemL.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} is stuck</source>
        <translation>{app} está bloqueado</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} (PID {pid}) has waited on a disk or device for %n min without progress, often a frozen network share or USB drive.</source>
        <translation>
            <numerusform>{app} (PID {pid}) lleva %n min esperando a un disco o dispositivo sin avanzar; suele ser una carpeta de red o una unidad USB colgada.</numerusform>
            <numerusform>{app} (PID {pid}) lleva %n min esperando a un disco o dispositivo sin avanzar; suele ser una carpeta de red o una unidad USB colgada.</numerusform>
        </translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.alertview</name>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Memory</source>
        <translation>Memoria</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when RAM use goes above</source>
        <translation>Avisa cuando el uso de RAM supera</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>CPU temperature</source>
        <translation>Temperatura de la CPU</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when the CPU gets hotter than</source>
        <translation>Avisa cuando la CPU supera</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>GPU temperature</source>
        <translation>Temperatura de la GPU</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when the graphics card gets hotter than</source>
        <translation>Avisa cuando la tarjeta gráfica supera</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Stuck apps</source>
        <translation>Apps bloqueadas</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when a window stays &quot;Not Responding&quot; in KWin, or one of your processes hangs on a disk or device with no progress, for</source>
        <translation>Avisa cuando una ventana sigue «No responde» en KWin, o uno de tus procesos se queda colgado en un disco o dispositivo sin avanzar, durante</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>min</source>
        <translation>min</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Test notification sent</source>
        <translation>Notificación de prueba enviada</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Couldn&apos;t send a notification: is the notification service running?</source>
        <translation>No se pudo enviar una notificación: ¿está funcionando el servicio de notificaciones?</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Send test notification</source>
        <translation>Enviar notificación de prueba</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Background alerts</source>
        <translation>Alertas en segundo plano</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>While a problem lasts, remind again after</source>
        <translation>Mientras dure un problema, recordarlo de nuevo tras</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Alerts</source>
        <translation>Alertas</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Disk free space</source>
        <translation>Espacio libre en disco</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Recent alerts</source>
        <translation>Alertas recientes</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>When</source>
        <translation>Cuándo</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Alert</source>
        <translation>Alerta</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Details</source>
        <translation>Detalles</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Nothing yet. Alerts show up here (and as notifications) when something crosses a line.</source>
        <translation>Nada todavía. Las alertas aparecen aquí (y como notificaciones) cuando algo cruza un límite.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>On: checked once a minute, even while SystemL is closed. Each alert notifies once, then waits until it clears or the reminder time passes.</source>
        <translation>Activadas: se comprueba una vez por minuto, incluso con SystemL cerrado. Cada alerta avisa una vez y espera hasta que se resuelva o pase el tiempo del recordatorio.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Off. Turn on to get notified in the background (adds a small systemd timer that runs once a minute).</source>
        <translation>Desactivadas. Actívalas para recibir avisos en segundo plano (añade un pequeño temporizador de systemd que se ejecuta una vez por minuto).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>{value} now</source>
        <translation>ahora {value}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>no CPU sensor found, so it stays quiet</source>
        <translation>no se encontró sensor de CPU, así que no avisará</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>no GPU sensor found, so it stays quiet</source>
        <translation>no se encontró sensor de GPU, así que no avisará</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>No disks found.</source>
        <translation>No se encontraron discos.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>{device} · {free} free of {total} · warns when free space drops below</source>
        <translation>{device} · {free} libres de {total} · avisa cuando el espacio libre baja de</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>on</source>
        <translation>activadas</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>off</source>
        <translation>desactivadas</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.page</name>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Overview</source>
        <translation>Resumen</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Processes</source>
        <translation>Procesos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Apps &amp; history</source>
        <translation>Apps e historial</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Services</source>
        <translation>Servicios</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Startup apps</source>
        <translation>Apps de inicio</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Disks</source>
        <translation>Discos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Alerts</source>
        <translation>Alertas</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Very high</source>
        <translation>Muy alta</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>High</source>
        <translation>Alta</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Normal</source>
        <translation>Normal</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Low</source>
        <translation>Baja</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Very low</source>
        <translation>Muy baja</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>running</source>
        <translation>en ejecución</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>sleeping</source>
        <translation>dormido</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>disk-sleep</source>
        <translation>esperando al disco</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>stopped</source>
        <translation>en pausa</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>tracing-stop</source>
        <translation>detenido por depuración</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>zombie</source>
        <translation>zombi</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>dead</source>
        <translation>terminado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>idle</source>
        <translation>inactivo</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>parked</source>
        <translation>aparcado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>waking</source>
        <translation>despertando</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>active</source>
        <translation>activo</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>inactive</source>
        <translation>inactivo</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>failed</source>
        <translation>fallido</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>activating</source>
        <translation>iniciándose</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>deactivating</source>
        <translation>deteniéndose</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>reloading</source>
        <translation>recargando</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>exited</source>
        <translation>finalizado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>waiting</source>
        <translation>esperando</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>listening</source>
        <translation>escuchando</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>auto-restart</source>
        <translation>reinicio automático</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>mounted</source>
        <translation>montado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>plugged</source>
        <translation>conectado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>enabled</source>
        <translation>habilitado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>disabled</source>
        <translation>deshabilitado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>static</source>
        <translation>estático</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>indirect</source>
        <translation>indirecto</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>masked</source>
        <translation>enmascarado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>generated</source>
        <translation>generado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>alias</source>
        <translation>alias</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>enabled-runtime</source>
        <translation>habilitado hasta reiniciar</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>linked</source>
        <translation>enlazado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Name</source>
        <translation>Nombre</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>User</source>
        <translation>Usuario</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>CPU</source>
        <translation>CPU</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Memory</source>
        <translation>Memoria</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Disk</source>
        <translation>Disco</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Threads</source>
        <translation>Hilos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Priority</source>
        <translation>Prioridad</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Status</source>
        <translation>Estado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Search name, command or PID</source>
        <translation>Buscar nombre, comando o PID</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Tree</source>
        <translation>Árbol</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Only mine</source>
        <translation>Solo los míos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Kernel threads</source>
        <translation>Hilos del kernel</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause</source>
        <translation>Pausar</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit</source>
        <translation>Forzar cierre</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End process</source>
        <translation>Terminar proceso</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Resume</source>
        <translation>Reanudar</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{name} · PID {pid} · started {when}</source>
        <translation>{name} · PID {pid} · iniciado {when}</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>%n process(es)</source>
        <translation>
            <numerusform>%n proceso</numerusform>
            <numerusform>%n procesos</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Show only this app</source>
        <translation>Mostrar solo esta app</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Open its folder</source>
        <translation>Abrir su carpeta</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit {name}</source>
        <translation>Forzar el cierre de {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End {name}</source>
        <translation>Terminar {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause {name}</source>
        <translation>Pausar {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit {name} (PID {pid})? Unsaved work in it will be lost.</source>
        <translation>¿Forzar el cierre de {name} (PID {pid})? Se perderá el trabajo sin guardar.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End {name} (PID {pid})? It gets the chance to save and close.</source>
        <translation>¿Terminar {name} (PID {pid})? Tendrá ocasión de guardar y cerrarse.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause {name} (PID {pid})? It freezes until you resume it; if other apps wait on it, they freeze too.</source>
        <translation>¿Pausar {name} (PID {pid})? Se congela hasta que lo reanudes; si otras apps dependen de él, también se congelan.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>It belongs to another user, so this asks for your password.</source>
        <translation>Pertenece a otro usuario, así que se te pedirá la contraseña.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{name} priority</source>
        <translation>prioridad de {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Now</source>
        <translation>Ahora</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Hour</source>
        <translation>Hora</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Day</source>
        <translation>Día</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Week</source>
        <translation>Semana</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MEMORY</source>
        <translation>MEMORIA</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>App</source>
        <translation>App</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Avg CPU</source>
        <translation>CPU media</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Peak CPU</source>
        <translation>CPU máxima</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Avg memory</source>
        <translation>Memoria media</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Peak memory</source>
        <translation>Memoria máxima</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Minutes</source>
        <translation>Minutos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Live, summed over every process of each app. Double-click one to see its processes.</source>
        <translation>En vivo, sumando todos los procesos de cada app. Haz doble clic en una para ver sus procesos.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>History is recorded while SystemL is open (busiest apps, once a minute, kept a week). {h} h {m} min recorded so far.</source>
        <translation>El historial se registra mientras SystemL está abierto (las apps más activas, una vez por minuto, se guarda una semana). Llevamos {h} h {m} min registrados.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Nothing recorded yet: history builds up minute by minute while SystemL is open.</source>
        <translation>Aún no hay nada registrado: el historial se va formando minuto a minuto mientras SystemL está abierto.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{app} · CPU</source>
        <translation>{app} · CPU</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{app} · MEMORY</source>
        <translation>{app} · MEMORIA</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>System</source>
        <translation>Sistema</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Yours</source>
        <translation>Tuyos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Search services</source>
        <translation>Buscar servicios</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Running only</source>
        <translation>Solo en ejecución</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Failed only</source>
        <translation>Solo fallidos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Service</source>
        <translation>Servicio</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>State</source>
        <translation>Estado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Startup</source>
        <translation>Inicio</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Description</source>
        <translation>Descripción</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Log</source>
        <translation>Registro</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start at boot</source>
        <translation>Iniciar al arrancar</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Don&apos;t start at boot</source>
        <translation>No iniciar al arrancar</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart</source>
        <translation>Reiniciar</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop</source>
        <translation>Detener</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start</source>
        <translation>Iniciar</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Loading services…</source>
        <translation>Cargando servicios…</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{shown} of %n service(s)</source>
        <translation>
            <numerusform>{shown} de %n servicio</numerusform>
            <numerusform>{shown} de %n servicios</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>%n failed</source>
        <translation>
            <numerusform>%n fallido</numerusform>
            <numerusform>%n fallidos</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{unit} keeps the system running, so it can&apos;t be stopped or restarted from here</source>
        <translation>{unit} mantiene el sistema en marcha, así que no se puede detener ni reiniciar desde aquí</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{unit} · system changes ask for your password</source>
        <translation>{unit} · los cambios del sistema piden tu contraseña</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop {unit}? Whatever depends on it may stop working.</source>
        <translation>¿Detener {unit}? Lo que dependa de él puede dejar de funcionar.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop starting {unit} at boot? Whatever depends on it may stop working.</source>
        <translation>¿Dejar de iniciar {unit} al arrancar? Lo que dependa de él puede dejar de funcionar.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart {unit}? Whatever depends on it may stop working for a moment.</source>
        <translation>¿Reiniciar {unit}? Lo que dependa de él puede dejar de funcionar un momento.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>NEEDED BY PLASMA</source>
        <translation>NECESARIO PARA PLASMA</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Remove</source>
        <translation>Quitar</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Apps and helpers that start when you log in. Turning one off writes an override in {folder}, the same way Plasma&apos;s settings do; turning it back on removes it.</source>
        <translation>Apps y ayudantes que se inician al iniciar sesión. Desactivar uno escribe una anulación en {folder}, igual que la configuración de Plasma; volver a activarlo la elimina.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Add app…</source>
        <translation>Añadir app…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Nothing starts at login besides Plasma itself.</source>
        <translation>Al iniciar sesión no arranca nada aparte de Plasma.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop {name} from starting at login and move its entry to the Trash?</source>
        <translation>¿Evitar que {name} se inicie al iniciar sesión y mover su entrada a la Papelera?</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Add to startup</source>
        <translation>Añadir al inicio</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start this app when you log in:</source>
        <translation>Iniciar esta app al iniciar sesión:</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>added</source>
        <translation>añadida</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>no file system</source>
        <translation>sin sistema de archivos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>not mounted</source>
        <translation>sin montar</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{used} of {total}</source>
        <translation>{used} de {total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Open</source>
        <translation>Abrir</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Unmount</source>
        <translation>Desmontar</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>read {read}   write {write}</source>
        <translation>lectura {read}   escritura {write}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Swap</source>
        <translation>Swap</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Failed services</source>
        <translation>Servicios fallidos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>used</source>
        <translation>en uso</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cache</source>
        <translation>caché</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>read</source>
        <translation>lectura</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>write</source>
        <translation>escritura</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Network</source>
        <translation>Red</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>down</source>
        <translation>bajada</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>up</source>
        <translation>subida</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Temperature</source>
        <translation>Temperatura</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Load average</source>
        <translation>Carga media</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Cores</source>
        <translation>Núcleos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Busiest right now</source>
        <translation>Más activos ahora</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Biggest in memory</source>
        <translation>Más memoria</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Quick actions</source>
        <translation>Acciones rápidas</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Empty swap into RAM</source>
        <translation>Vaciar la swap en la RAM</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Moves everything in swap back into memory when it fits (asks for your password). Handy after a big game when the desktop feels sluggish.</source>
        <translation>Devuelve todo lo que hay en la swap a la memoria si cabe (pide tu contraseña). Útil tras un juego grande, cuando el escritorio va lento.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart Plasma desktop</source>
        <translation>Reiniciar el escritorio Plasma</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restarts the panel and desktop without logging out. Open apps keep running.</source>
        <translation>Reinicia el panel y el escritorio sin cerrar sesión. Las apps abiertas siguen funcionando.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Clear failed services</source>
        <translation>Limpiar servicios fallidos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Forgets your user services&apos; failed state so the count starts fresh.</source>
        <translation>Olvida el estado de fallo de tus servicios de usuario para que la cuenta empiece de cero.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Open OptimizeL</source>
        <translation>Abrir OptimizeL</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Speed tweaks for this PC as on/off switches.</source>
        <translation>Ajustes de velocidad para este PC como interruptores.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>This PC</source>
        <translation>Este PC</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Show its processes</source>
        <translation>Ver sus procesos</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>of {total}</source>
        <translation>de {total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>no swap</source>
        <translation>sin swap</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>5 min {five} · 15 min {fifteen}</source>
        <translation>5 min {five} · 15 min {fifteen}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MONITOR</source>
        <translation>MONITOR</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MANAGE</source>
        <translation>GESTIONAR</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Up {time}
Load {load}</source>
        <translation>Encendido {time}
Carga {load}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>done</source>
        <translation>hecho</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cancelled</source>
        <translation>cancelado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{what}: {result}</source>
        <translation>{what}: {result}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Couldn&apos;t change {what}: {error}</source>
        <translation>No se pudo cambiar {what}: {error}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{unit} log</source>
        <translation>Registro de {unit}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Empty swap</source>
        <translation>Vaciar swap</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Move everything in swap back into RAM? This asks for your password and only runs when there&apos;s room.</source>
        <translation>¿Devolver todo lo que hay en la swap a la RAM? Pide tu contraseña y solo se ejecuta si hay espacio.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>emptied into RAM</source>
        <translation>vaciada en la RAM</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart Plasma</source>
        <translation>Reiniciar Plasma</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart the Plasma desktop and panel? Your open apps keep running.</source>
        <translation>¿Reiniciar el escritorio y el panel de Plasma? Tus apps abiertas siguen funcionando.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>restarted</source>
        <translation>reiniciado</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cleared · %n failed system service(s) left</source>
        <translation>
            <numerusform>limpiado · queda %n servicio del sistema fallido</numerusform>
            <numerusform>limpiado · quedan %n servicios del sistema fallidos</numerusform>
        </translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.probe</name>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>%n core(s)</source>
        <translation>
            <numerusform>%n núcleo</numerusform>
            <numerusform>%n núcleos</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>%n thread(s)</source>
        <translation>
            <numerusform>%n hilo</numerusform>
            <numerusform>%n hilos</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>System</source>
        <translation>Sistema</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Kernel</source>
        <translation>Kernel</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Desktop</source>
        <translation>Escritorio</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>CPU</source>
        <translation>CPU</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Memory</source>
        <translation>Memoria</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>{d} d {h} h {m} min</source>
        <translation>{d} d {h} h {m} min</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>{h} h {m} min</source>
        <translation>{h} h {m} min</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>{m} min</source>
        <translation>{m} min</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.system</name>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>the helper failed ({code})</source>
        <translation>el ayudante falló ({code})</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>that process can&apos;t be stopped from here</source>
        <translation>ese proceso no se puede detener desde aquí</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>already gone</source>
        <translation>ya no existe</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>{name} keeps your session running; not stopping it</source>
        <translation>{name} mantiene tu sesión en marcha; no se detendrá</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>done</source>
        <translation>hecho</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>systemctl {action} failed</source>
        <translation>systemctl {action} falló</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>Couldn&apos;t read the log.</source>
        <translation>No se pudo leer el registro.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>No log lines yet.</source>
        <translation>Aún no hay líneas en el registro.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>Plasma needs this to start; leaving it on</source>
        <translation>Plasma lo necesita para arrancar; se queda activado</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>only your own startup entries can be removed</source>
        <translation>solo se pueden quitar tus propias entradas de inicio</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>USB drive</source>
        <translation>Unidad USB</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>Hard drive</source>
        <translation>Disco duro</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>couldn&apos;t unmount</source>
        <translation>no se pudo desmontar</translation>
    </message>
</context>
</TS>
