<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="fr" sourcelanguage="en">
<context>
    <name>grimoire.spells.systeml.alerts</name>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} uses the most ({size} GB).</source>
        <translation>{app} en utilise le plus ({size} Go).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>SystemL alerts work</source>
        <translation>Les alertes de SystemL fonctionnent</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>This is how memory, temperature, disk and stuck-app alerts will look.</source>
        <translation>Voici à quoi ressembleront les alertes de mémoire, de température, de disque et d’application bloquée.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>RAM is {percent}% used ({used} of {total} GB).</source>
        <translation>La mémoire est utilisée à {percent} % ({used} sur {total} Go).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>Memory almost full</source>
        <translation>Mémoire presque pleine</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>CPU is running hot</source>
        <translation>Le processeur chauffe</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>CPU temperature is {now}°C (alert at {limit}°C).</source>
        <translation>Le processeur est à {now} °C (alerte à {limit} °C).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>GPU is running hot</source>
        <translation>La carte graphique chauffe</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>GPU temperature is {now}°C (alert at {limit}°C).</source>
        <translation>La carte graphique est à {now} °C (alerte à {limit} °C).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{mount} is almost full</source>
        <translation>{mount} est presque plein</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{mount} has {free} GB free ({percent}%; alert below {limit}).</source>
        <translation>{mount} a {free} Go libres ({percent} % ; alerte sous {limit}).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} isn&apos;t responding</source>
        <translation>{app} ne répond pas</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>An app isn&apos;t responding</source>
        <translation>Une application ne répond pas</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>It hasn&apos;t responded for %n min. Wait a little, or close it from its window or SystemL&apos;s Processes.</source>
        <translation>
            <numerusform>Elle ne répond plus depuis %n min. Patientez un peu, ou fermez-la depuis sa fenêtre ou depuis les Processus de SystemL.</numerusform>
            <numerusform>Elle ne répond plus depuis %n min. Patientez un peu, ou fermez-la depuis sa fenêtre ou depuis les Processus de SystemL.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} is stuck</source>
        <translation>{app} est bloqué</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/alerts.py"/>
        <source>{app} (PID {pid}) has waited on a disk or device for %n min without progress, often a frozen network share or USB drive.</source>
        <translation>
            <numerusform>{app} (PID {pid}) attend un disque ou un périphérique depuis %n min sans progresser, souvent un partage réseau ou une clé USB figés.</numerusform>
            <numerusform>{app} (PID {pid}) attend un disque ou un périphérique depuis %n min sans progresser, souvent un partage réseau ou une clé USB figés.</numerusform>
        </translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.alertview</name>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Memory</source>
        <translation>Mémoire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when RAM use goes above</source>
        <translation>Prévient quand l’utilisation de la mémoire dépasse</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>CPU temperature</source>
        <translation>Température du processeur</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when the CPU gets hotter than</source>
        <translation>Prévient quand le processeur dépasse</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>GPU temperature</source>
        <translation>Température de la carte graphique</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when the graphics card gets hotter than</source>
        <translation>Prévient quand la carte graphique dépasse</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Stuck apps</source>
        <translation>Applications bloquées</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Warns when a window stays &quot;Not Responding&quot; in KWin, or one of your processes hangs on a disk or device with no progress, for</source>
        <translation>Prévient quand une fenêtre reste « Ne répond pas » dans KWin, ou qu’un de vos processus reste bloqué sur un disque ou un périphérique sans progresser, pendant</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>min</source>
        <translation>min</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Test notification sent</source>
        <translation>Notification de test envoyée</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Couldn&apos;t send a notification: is the notification service running?</source>
        <translation>Impossible d’envoyer une notification : le service de notifications est-il lancé ?</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Send test notification</source>
        <translation>Envoyer une notification de test</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Background alerts</source>
        <translation>Alertes en arrière-plan</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>While a problem lasts, remind again after</source>
        <translation>Tant qu’un problème dure, rappeler après</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Alerts</source>
        <translation>Alertes</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Disk free space</source>
        <translation>Espace libre des disques</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Recent alerts</source>
        <translation>Alertes récentes</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>When</source>
        <translation>Quand</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Alert</source>
        <translation>Alerte</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Details</source>
        <translation>Détails</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Nothing yet. Alerts show up here (and as notifications) when something crosses a line.</source>
        <translation>Rien pour l’instant. Les alertes s’affichent ici (et en notification) quand quelque chose dépasse un seuil.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>On: checked once a minute, even while SystemL is closed. Each alert notifies once, then waits until it clears or the reminder time passes.</source>
        <translation>Activées : vérification une fois par minute, même quand SystemL est fermé. Chaque alerte prévient une fois, puis attend que le problème disparaisse ou que le délai de rappel passe.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>Off. Turn on to get notified in the background (adds a small systemd timer that runs once a minute).</source>
        <translation>Désactivées. Activez-les pour être prévenu en arrière-plan (ajoute un petit minuteur systemd qui tourne une fois par minute).</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>{value} now</source>
        <translation>{value} actuellement</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>no CPU sensor found, so it stays quiet</source>
        <translation>aucun capteur de processeur trouvé, donc pas d’alerte</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>no GPU sensor found, so it stays quiet</source>
        <translation>aucun capteur de carte graphique trouvé, donc pas d’alerte</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>No disks found.</source>
        <translation>Aucun disque trouvé.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>{device} · {free} free of {total} · warns when free space drops below</source>
        <translation>{device} · {free} libres sur {total} · prévient quand l’espace libre passe sous</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>on</source>
        <translation>activées</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/alertview.py"/>
        <source>off</source>
        <translation>désactivées</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.page</name>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Overview</source>
        <translation>Vue d’ensemble</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Processes</source>
        <translation>Processus</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Apps &amp; history</source>
        <translation>Applications et historique</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Services</source>
        <translation>Services</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Startup apps</source>
        <translation>Applications au démarrage</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Disks</source>
        <translation>Disques</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Alerts</source>
        <translation>Alertes</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Very high</source>
        <translation>Très haute</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>High</source>
        <translation>Haute</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Normal</source>
        <translation>Normale</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Low</source>
        <translation>Basse</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Very low</source>
        <translation>Très basse</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>running</source>
        <translation>en cours</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>sleeping</source>
        <translation>en veille</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>disk-sleep</source>
        <translation>attend le disque</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>stopped</source>
        <translation>en pause</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>tracing-stop</source>
        <translation>arrêté par le débogueur</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>zombie</source>
        <translation>zombie</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>dead</source>
        <translation>terminé</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>idle</source>
        <translation>inactif</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>parked</source>
        <translation>parqué</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>waking</source>
        <translation>se réveille</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>active</source>
        <translation>actif</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>inactive</source>
        <translation>inactif</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>failed</source>
        <translation>en échec</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>activating</source>
        <translation>démarrage</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>deactivating</source>
        <translation>arrêt</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>reloading</source>
        <translation>rechargement</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>exited</source>
        <translation>terminé</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>waiting</source>
        <translation>en attente</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>listening</source>
        <translation>en écoute</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>auto-restart</source>
        <translation>redémarrage auto</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>mounted</source>
        <translation>monté</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>plugged</source>
        <translation>branché</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>enabled</source>
        <translation>activé</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>disabled</source>
        <translation>désactivé</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>static</source>
        <translation>statique</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>indirect</source>
        <translation>indirect</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>masked</source>
        <translation>masqué</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>generated</source>
        <translation>généré</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>alias</source>
        <translation>alias</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>enabled-runtime</source>
        <translation>activé jusqu’au redémarrage</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>linked</source>
        <translation>lié</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Name</source>
        <translation>Nom</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>User</source>
        <translation>Utilisateur</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>CPU</source>
        <translation>Processeur</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Memory</source>
        <translation>Mémoire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Disk</source>
        <translation>Disque</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Threads</source>
        <translation>Threads</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Priority</source>
        <translation>Priorité</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Status</source>
        <translation>État</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Search name, command or PID</source>
        <translation>Rechercher un nom, une commande ou un PID</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Tree</source>
        <translation>Arbre</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Only mine</source>
        <translation>Les miens seulement</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Kernel threads</source>
        <translation>Threads du noyau</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause</source>
        <translation>Mettre en pause</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit</source>
        <translation>Forcer à quitter</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End process</source>
        <translation>Terminer le processus</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Resume</source>
        <translation>Reprendre</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{name} · PID {pid} · started {when}</source>
        <translation>{name} · PID {pid} · lancé le {when}</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>%n process(es)</source>
        <translation>
            <numerusform>%n processus</numerusform>
            <numerusform>%n processus</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Show only this app</source>
        <translation>Afficher seulement cette application</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Open its folder</source>
        <translation>Ouvrir son dossier</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit {name}</source>
        <translation>Forcer {name} à quitter</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End {name}</source>
        <translation>Terminer {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause {name}</source>
        <translation>Mettre {name} en pause</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Force quit {name} (PID {pid})? Unsaved work in it will be lost.</source>
        <translation>Forcer {name} (PID {pid}) à quitter ? Le travail non enregistré sera perdu.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>End {name} (PID {pid})? It gets the chance to save and close.</source>
        <translation>Terminer {name} (PID {pid}) ? Il aura le temps d’enregistrer et de se fermer.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Pause {name} (PID {pid})? It freezes until you resume it; if other apps wait on it, they freeze too.</source>
        <translation>Mettre {name} (PID {pid}) en pause ? Il se fige jusqu’à ce que vous le repreniez ; si d’autres applications l’attendent, elles se figent aussi.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>It belongs to another user, so this asks for your password.</source>
        <translation>Il appartient à un autre utilisateur, votre mot de passe sera donc demandé.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{name} priority</source>
        <translation>priorité de {name}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Now</source>
        <translation>Maintenant</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Hour</source>
        <translation>Heure</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Day</source>
        <translation>Jour</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Week</source>
        <translation>Semaine</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MEMORY</source>
        <translation>MÉMOIRE</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>App</source>
        <translation>Application</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Avg CPU</source>
        <translation>Processeur moyen</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Peak CPU</source>
        <translation>Pic processeur</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Avg memory</source>
        <translation>Mémoire moyenne</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Peak memory</source>
        <translation>Pic mémoire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Minutes</source>
        <translation>Minutes</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Live, summed over every process of each app. Double-click one to see its processes.</source>
        <translation>En direct, en additionnant tous les processus de chaque application. Double-cliquez sur l’une d’elles pour voir ses processus.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>History is recorded while SystemL is open (busiest apps, once a minute, kept a week). {h} h {m} min recorded so far.</source>
        <translation>L’historique est enregistré tant que SystemL est ouvert (les applications les plus actives, une fois par minute, gardé une semaine). {h} h {m} min enregistrées jusqu’ici.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Nothing recorded yet: history builds up minute by minute while SystemL is open.</source>
        <translation>Rien d’enregistré pour l’instant : l’historique se construit minute après minute tant que SystemL est ouvert.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{app} · CPU</source>
        <translation>{app} · PROCESSEUR</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{app} · MEMORY</source>
        <translation>{app} · MÉMOIRE</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>System</source>
        <translation>Système</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Yours</source>
        <translation>Les vôtres</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Search services</source>
        <translation>Rechercher des services</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Running only</source>
        <translation>En cours seulement</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Failed only</source>
        <translation>En échec seulement</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Service</source>
        <translation>Service</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>State</source>
        <translation>État</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Startup</source>
        <translation>Démarrage</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Description</source>
        <translation>Description</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Log</source>
        <translation>Journal</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start at boot</source>
        <translation>Lancer au démarrage</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Don&apos;t start at boot</source>
        <translation>Ne pas lancer au démarrage</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart</source>
        <translation>Redémarrer</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop</source>
        <translation>Arrêter</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start</source>
        <translation>Démarrer</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Loading services…</source>
        <translation>Chargement des services…</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{shown} of %n service(s)</source>
        <translation>
            <numerusform>{shown} sur %n service</numerusform>
            <numerusform>{shown} sur %n services</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>%n failed</source>
        <translation>
            <numerusform>%n en échec</numerusform>
            <numerusform>%n en échec</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{unit} keeps the system running, so it can&apos;t be stopped or restarted from here</source>
        <translation>{unit} fait tourner le système : il ne peut pas être arrêté ni redémarré d’ici</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{unit} · system changes ask for your password</source>
        <translation>{unit} · les modifications du système demandent votre mot de passe</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop {unit}? Whatever depends on it may stop working.</source>
        <translation>Arrêter {unit} ? Ce qui en dépend risque de ne plus fonctionner.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop starting {unit} at boot? Whatever depends on it may stop working.</source>
        <translation>Ne plus lancer {unit} au démarrage ? Ce qui en dépend risque de ne plus fonctionner.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart {unit}? Whatever depends on it may stop working for a moment.</source>
        <translation>Redémarrer {unit} ? Ce qui en dépend risque de ne plus fonctionner un instant.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>NEEDED BY PLASMA</source>
        <translation>REQUIS PAR PLASMA</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Remove</source>
        <translation>Retirer</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Apps and helpers that start when you log in. Turning one off writes an override in {folder}, the same way Plasma&apos;s settings do; turning it back on removes it.</source>
        <translation>Les applications et assistants lancés à l’ouverture de session. En désactiver un écrit une surcharge dans {folder}, comme le font les paramètres de Plasma ; le réactiver la supprime.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Add app…</source>
        <translation>Ajouter une application…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Nothing starts at login besides Plasma itself.</source>
        <translation>Rien ne se lance à l’ouverture de session à part Plasma lui-même.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Stop {name} from starting at login and move its entry to the Trash?</source>
        <translation>Ne plus lancer {name} à l’ouverture de session et mettre son entrée à la corbeille ?</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Add to startup</source>
        <translation>Ajouter au démarrage</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Start this app when you log in:</source>
        <translation>Lancer cette application à l’ouverture de session :</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>added</source>
        <translation>ajoutée</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>no file system</source>
        <translation>aucun système de fichiers</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>not mounted</source>
        <translation>non monté</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{used} of {total}</source>
        <translation>{used} sur {total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Open</source>
        <translation>Ouvrir</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Unmount</source>
        <translation>Démonter</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>read {read}   write {write}</source>
        <translation>lecture {read}   écriture {write}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Swap</source>
        <translation>Swap</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Failed services</source>
        <translation>Services en échec</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>used</source>
        <translation>utilisée</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cache</source>
        <translation>cache</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>read</source>
        <translation>lecture</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>write</source>
        <translation>écriture</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Network</source>
        <translation>Réseau</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>down</source>
        <translation>réception</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>up</source>
        <translation>envoi</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Temperature</source>
        <translation>Température</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Load average</source>
        <translation>Charge moyenne</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Cores</source>
        <translation>Cœurs</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Busiest right now</source>
        <translation>Les plus actifs en ce moment</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Biggest in memory</source>
        <translation>Les plus gros en mémoire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Quick actions</source>
        <translation>Actions rapides</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Empty swap into RAM</source>
        <translation>Vider le swap dans la mémoire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Moves everything in swap back into memory when it fits (asks for your password). Handy after a big game when the desktop feels sluggish.</source>
        <translation>Remet tout le contenu du swap en mémoire quand il y a la place (demande votre mot de passe). Pratique après un gros jeu, quand le bureau semble lent.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart Plasma desktop</source>
        <translation>Redémarrer le bureau Plasma</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restarts the panel and desktop without logging out. Open apps keep running.</source>
        <translation>Redémarre le tableau de bord et le bureau sans fermer la session. Les applications ouvertes continuent de tourner.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Clear failed services</source>
        <translation>Effacer les services en échec</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Forgets your user services&apos; failed state so the count starts fresh.</source>
        <translation>Oublie l’état d’échec de vos services utilisateur pour que le compte reparte de zéro.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Open OptimizeL</source>
        <translation>Ouvrir OptimizeL</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Speed tweaks for this PC as on/off switches.</source>
        <translation>Des réglages de vitesse pour ce PC, sous forme d’interrupteurs.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>This PC</source>
        <translation>Ce PC</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Show its processes</source>
        <translation>Voir ses processus</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>of {total}</source>
        <translation>sur {total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>no swap</source>
        <translation>pas de swap</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>5 min {five} · 15 min {fifteen}</source>
        <translation>5 min {five} · 15 min {fifteen}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MONITOR</source>
        <translation>SURVEILLER</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>MANAGE</source>
        <translation>GÉRER</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Up {time}
Load {load}</source>
        <translation>Allumé depuis {time}
Charge {load}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>done</source>
        <translation>fait</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cancelled</source>
        <translation>annulé</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{what}: {result}</source>
        <translation>{what} : {result}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Couldn&apos;t change {what}: {error}</source>
        <translation>Impossible de modifier {what} : {error}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>{unit} log</source>
        <translation>Journal de {unit}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Empty swap</source>
        <translation>Vider le swap</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Move everything in swap back into RAM? This asks for your password and only runs when there&apos;s room.</source>
        <translation>Remettre tout le contenu du swap en mémoire ? Votre mot de passe sera demandé, et cela ne se fait que s’il y a la place.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>emptied into RAM</source>
        <translation>vidé dans la mémoire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart Plasma</source>
        <translation>Redémarrer Plasma</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Restart the Plasma desktop and panel? Your open apps keep running.</source>
        <translation>Redémarrer le bureau et le tableau de bord de Plasma ? Vos applications ouvertes continuent de tourner.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>restarted</source>
        <translation>redémarré</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>cleared · %n failed system service(s) left</source>
        <translation>
            <numerusform>effacé · il reste %n service système en échec</numerusform>
            <numerusform>effacé · il reste %n services système en échec</numerusform>
        </translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.probe</name>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>%n core(s)</source>
        <translation>
            <numerusform>%n cœur</numerusform>
            <numerusform>%n cœurs</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>%n thread(s)</source>
        <translation>
            <numerusform>%n thread</numerusform>
            <numerusform>%n threads</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>System</source>
        <translation>Système</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Kernel</source>
        <translation>Noyau</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Desktop</source>
        <translation>Bureau</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>CPU</source>
        <translation>Processeur</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>Memory</source>
        <translation>Mémoire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/probe.py"/>
        <source>{d} d {h} h {m} min</source>
        <translation>{d} j {h} h {m} min</translation>
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
        <translation>l’assistant a échoué ({code})</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>that process can&apos;t be stopped from here</source>
        <translation>ce processus ne peut pas être arrêté d’ici</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>already gone</source>
        <translation>déjà terminé</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>{name} keeps your session running; not stopping it</source>
        <translation>{name} fait tourner votre session ; il ne sera pas arrêté</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>done</source>
        <translation>fait</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>systemctl {action} failed</source>
        <translation>échec de systemctl {action}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>Couldn&apos;t read the log.</source>
        <translation>Impossible de lire le journal.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>No log lines yet.</source>
        <translation>Le journal est encore vide.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>Plasma needs this to start; leaving it on</source>
        <translation>Plasma en a besoin pour démarrer ; il reste activé</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>only your own startup entries can be removed</source>
        <translation>seules vos propres entrées de démarrage peuvent être retirées</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>USB drive</source>
        <translation>Clé ou disque USB</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>Hard drive</source>
        <translation>Disque dur</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>couldn&apos;t unmount</source>
        <translation>impossible de démonter</translation>
    </message>
</context>
</TS>
