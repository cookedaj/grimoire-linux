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
    <name>grimoire.spells.systeml.drives</name>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Drive actions need python3-dbus: {command}</source>
        <translation>Les actions sur les disques nécessitent python3-dbus : {command}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>not allowed (polkit refused)</source>
        <translation>non autorisé (polkit a refusé)</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>it&apos;s in use: close the files and apps using it, then try again</source>
        <translation>il est utilisé : fermez les fichiers et applications qui s&apos;en servent, puis réessayez</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>udisks2 isn&apos;t running</source>
        <translation>udisks2 ne fonctionne pas</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>USB drive</source>
        <translation>Clé USB</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Hard drive</source>
        <translation>Disque dur</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Optical drive</source>
        <translation>Lecteur optique</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Memory card</source>
        <translation>Carte mémoire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>Virtual disk</source>
        <translation>Disque virtuel</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>not a udisks device</source>
        <translation>ce n&apos;est pas un périphérique udisks</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>the system runs from it, so it stays mounted</source>
        <translation>le système fonctionne dessus, il reste donc monté</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>unmounted</source>
        <translation>démonté</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>the system runs from this drive</source>
        <translation>le système fonctionne depuis ce disque</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>safe to unplug</source>
        <translation>peut être débranché en toute sécurité</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>ejected</source>
        <translation>éjecté</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>unmounted; safe to unplug</source>
        <translation>démonté ; peut être débranché en toute sécurité</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>This drive doesn&apos;t report its health to udisks.</source>
        <translation>Ce disque ne transmet pas son état de santé à udisks.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>smartctl needs root to read this drive; udisks has no health data for it.</source>
        <translation>smartctl a besoin des droits root pour lire ce disque ; udisks n&apos;a pas de données de santé pour lui.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/drives.py"/>
        <source>No health data for this drive.</source>
        <translation>Aucune donnée de santé pour ce disque.</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.driveview</name>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Temperature</source>
        <translation>Température</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Powered on</source>
        <translation>Temps de fonctionnement</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Bad sectors</source>
        <translation>Secteurs défectueux</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Wear (of rated life)</source>
        <translation>Usure (de la durée de vie prévue)</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Spare blocks left</source>
        <translation>Blocs de réserve restants</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Spare warning level</source>
        <translation>Seuil d&apos;alerte de réserve</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Data written</source>
        <translation>Données écrites</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Data read</source>
        <translation>Données lues</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Power cycles</source>
        <translation>Cycles d&apos;alimentation</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Unsafe shutdowns</source>
        <translation>Arrêts brutaux</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Media errors</source>
        <translation>Erreurs de support</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Error log entries</source>
        <translation>Entrées du journal d&apos;erreurs</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Sensors</source>
        <translation>Capteurs</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Last self-test</source>
        <translation>Dernier autotest</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>passed</source>
        <translation>réussi</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>running</source>
        <translation>en cours</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>aborted</source>
        <translation>abandonné</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>interrupted</source>
        <translation>interrompu</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>encrypted, locked</source>
        <translation>chiffré, verrouillé</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>encrypted · {fs}</source>
        <translation>chiffré · {fs}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>swap</source>
        <translation>swap</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>extended</source>
        <translation>étendue</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>no file system</source>
        <translation>aucun système de fichiers</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Health unknown</source>
        <translation>Santé inconnue</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Failing</source>
        <translation>Défaillant</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Healthy</source>
        <translation>En bonne santé</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Health of {drive}</source>
        <translation>Santé de {drive}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>serial {serial}</source>
        <translation>n° de série {serial}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>firmware {version}</source>
        <translation>micrologiciel {version}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Reading health data…</source>
        <translation>Lecture des données de santé…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Attribute</source>
        <translation>Attribut</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Value</source>
        <translation>Valeur</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Worst</source>
        <translation>Pire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Threshold</source>
        <translation>Seuil</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Raw</source>
        <translation>Brut</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Close</source>
        <translation>Fermer</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Healthy: the drive reports no problems.</source>
        <translation>En bonne santé : le disque ne signale aucun problème.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Failing: back up what&apos;s on it now and plan to replace it.</source>
        <translation>Défaillant : sauvegardez son contenu maintenant et prévoyez de le remplacer.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Warning from the drive: {warning}</source>
        <translation>Avertissement du disque : {warning}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Read with smartctl.</source>
        <translation>Lu avec smartctl.</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>%n hour(s)</source>
        <translation>
            <numerusform>%n heure</numerusform>
            <numerusform>%n heures</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>SYSTEM</source>
        <translation>SYSTÈME</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Show the drive&apos;s health report (SMART)</source>
        <translation>Afficher le rapport de santé du disque (SMART)</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Eject</source>
        <translation>Éjecter</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Safely remove</source>
        <translation>Retirer en toute sécurité</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Unmounts everything on it, then powers it off so it can be unplugged</source>
        <translation>Démonte tout ce qu&apos;il contient, puis l&apos;éteint pour qu&apos;il puisse être débranché</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>No media</source>
        <translation>Aucun support</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>No partitions or file systems on this drive.</source>
        <translation>Aucune partition ni aucun système de fichiers sur ce disque.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>not mounted</source>
        <translation>non monté</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Open</source>
        <comment>verb</comment>
        <translation>Ouvrir</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Open in VaultL</source>
        <translation>Ouvrir dans VaultL</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Unmount</source>
        <translation>Démonter</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>The system runs from it, so it stays mounted</source>
        <translation>Le système fonctionne dessus, il reste donc monté</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Mount</source>
        <translation>Monter</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>{used} of {total}</source>
        <translation>{used} sur {total}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Formatting and partitions</source>
        <translation>Formatage et partitions</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Creating, resizing, formatting and deleting partitions can erase a whole disk, so SystemL leaves them to KDE Partition Manager, which checks every step and asks for your password.</source>
        <translation>Créer, redimensionner, formater et supprimer des partitions peut effacer un disque entier : SystemL laisse donc cela au Gestionnaire de partitions de KDE, qui vérifie chaque étape et demande votre mot de passe.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>It isn&apos;t installed: {command}</source>
        <translation>Il n&apos;est pas installé : {command}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Open Partition Manager</source>
        <translation>Ouvrir le Gestionnaire de partitions</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>udisks2 isn&apos;t available, so drives are listed read-only (from lsblk): nothing can be mounted or removed from here.</source>
        <translation>udisks2 n&apos;est pas disponible : les disques sont affichés en lecture seule (depuis lsblk) et rien ne peut être monté ou retiré d&apos;ici.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>No drives found.</source>
        <translation>Aucun disque trouvé.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>read {read}   write {write}</source>
        <translation>lecture {read}   écriture {write}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>mounted at {folder}</source>
        <translation>monté dans {folder}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/driveview.py"/>
        <source>Couldn&apos;t start KDE Partition Manager.</source>
        <translation>Impossible de lancer le Gestionnaire de partitions de KDE.</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.journal</name>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Emergency</source>
        <translation>Urgence</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Alert</source>
        <translation>Alerte</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Critical</source>
        <translation>Critique</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Error</source>
        <translation>Erreur</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Warning</source>
        <translation>Avertissement</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Notice</source>
        <translation>Notice</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Info</source>
        <translation>Info</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Debug</source>
        <translation>Débogage</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>Couldn&apos;t run journalctl: {error}</source>
        <translation>Impossible de lancer journalctl : {error}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/journal.py"/>
        <source>journalctl stopped ({code})</source>
        <translation>journalctl s&apos;est arrêté ({code})</translation>
    </message>
</context>
<context>
    <name>grimoire.spells.systeml.logview</name>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Time</source>
        <translation>Heure</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Level</source>
        <translation>Niveau</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Source</source>
        <translation>Source</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Message</source>
        <translation>Message</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>All levels</source>
        <translation>Tous les niveaux</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Critical and worse</source>
        <translation>Critique et pire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Errors and worse</source>
        <translation>Erreurs et pire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Warnings and worse</source>
        <translation>Avertissements et pire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Notices and worse</source>
        <translation>Notices et pire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Everything but debug</source>
        <translation>Tout sauf le débogage</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Any time</source>
        <translation>N&apos;importe quand</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last 15 minutes</source>
        <translation>15 dernières minutes</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last hour</source>
        <translation>Dernière heure</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last 24 hours</source>
        <translation>Dernières 24 heures</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last 7 days</source>
        <translation>7 derniers jours</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Custom range…</source>
        <translation>Période personnalisée…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Yours</source>
        <translation>Les vôtres</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>System</source>
        <translation>Système</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Messages from the system and its services</source>
        <translation>Messages du système et de ses services</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only members of the systemd-journal or adm group can read the system journal. To join: {command}, then log out and back in.</source>
        <translation>Seuls les membres du groupe systemd-journal ou adm peuvent lire le journal du système. Pour le rejoindre : {command}, puis déconnectez-vous et reconnectez-vous.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Search messages</source>
        <translation>Rechercher dans les messages</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Keep reading: new messages appear as they&apos;re written</source>
        <translation>Continuer la lecture : les nouveaux messages s&apos;affichent dès qu&apos;ils sont écrits</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Follow</source>
        <translation>Suivre</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Any unit or app</source>
        <translation>N&apos;importe quelle unité ou application</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Last %n entries</source>
        <translation>
            <numerusform>%n dernière entrée</numerusform>
            <numerusform>%n dernières entrées</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Lowest level to show</source>
        <translation>Niveau minimal à afficher</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Which boot</source>
        <translation>Quel démarrage</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Time range</source>
        <translation>Période</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only this unit or app</source>
        <translation>Seulement cette unité ou application</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>How many of the newest entries to read</source>
        <translation>Combien d&apos;entrées les plus récentes lire</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>From</source>
        <translation>Du</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>to</source>
        <translation>au</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Pick a line to see every field the journal keeps for it.</source>
        <translation>Choisissez une ligne pour voir tous les champs que le journal garde pour elle.</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy</source>
        <translation>Copier</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy the selected lines ({key})</source>
        <translation>Copier les lignes sélectionnées ({key})</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Export…</source>
        <translation>Exporter…</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Save the lines shown to a text or JSON file ({key})</source>
        <translation>Enregistrer les lignes affichées dans un fichier texte ou JSON ({key})</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Reload</source>
        <translation>Recharger</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>This boot</source>
        <translation>Ce démarrage</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Boot of {when}</source>
        <translation>Démarrage du {when}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>All boots</source>
        <translation>Tous les démarrages</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>journalctl: {error}</source>
        <translation>journalctl : {error}</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Reading the journal… %n entries so far</source>
        <translation>
            <numerusform>Lecture du journal… %n entrée pour l&apos;instant</numerusform>
            <numerusform>Lecture du journal… %n entrées pour l&apos;instant</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Following · %n entries</source>
        <translation>
            <numerusform>Suivi · %n entrée</numerusform>
            <numerusform>Suivi · %n entrées</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Nothing matches these filters.</source>
        <translation>Rien ne correspond à ces filtres.</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>%n entries</source>
        <translation>
            <numerusform>%n entrée</numerusform>
            <numerusform>%n entrées</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>%n selected</source>
        <translation>
            <numerusform>%n sélectionnée</numerusform>
            <numerusform>%n sélectionnées</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>%n line(s) copied</source>
        <translation>
            <numerusform>%n ligne copiée</numerusform>
            <numerusform>%n lignes copiées</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy selected lines</source>
        <translation>Copier les lignes sélectionnées</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy message</source>
        <translation>Copier le message</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Copy all fields</source>
        <translation>Copier tous les champs</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only {unit}</source>
        <translation>Seulement {unit}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Only {app}</source>
        <translation>Seulement {app}</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Every unit and app</source>
        <translation>Toutes les unités et applications</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Text (*.txt *.log);;JSON lines (*.jsonl *.json)</source>
        <translation>Texte (*.txt *.log);;Lignes JSON (*.jsonl *.json)</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Export log</source>
        <translation>Exporter le journal</translation>
    </message>
    <message numerus="yes">
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Saved %n line(s) to {path}</source>
        <translation>
            <numerusform>%n ligne enregistrée dans {path}</numerusform>
            <numerusform>%n lignes enregistrées dans {path}</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/logview.py"/>
        <source>Couldn&apos;t save the log: {error}</source>
        <translation>Impossible d&apos;enregistrer le journal : {error}</translation>
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
        <source>Drives</source>
        <translation>Disques</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/page.py"/>
        <source>Logs</source>
        <translation>Journaux</translation>
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
        <source>{used} of {total}</source>
        <translation>{used} sur {total}</translation>
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
    <message>
        <source>{unit} log</source>
        <translation type="vanished">Journal de {unit}</translation>
    </message>
    <message>
        <source>Disks</source>
        <translation type="vanished">Disques</translation>
    </message>
    <message>
        <source>no file system</source>
        <translation type="vanished">aucun système de fichiers</translation>
    </message>
    <message>
        <source>not mounted</source>
        <translation type="vanished">non monté</translation>
    </message>
    <message>
        <source>Open</source>
        <translation type="vanished">Ouvrir</translation>
    </message>
    <message>
        <source>Unmount</source>
        <translation type="vanished">Démonter</translation>
    </message>
    <message>
        <source>read {read}   write {write}</source>
        <translation type="vanished">lecture {read}   écriture {write}</translation>
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
        <source>Plasma needs this to start; leaving it on</source>
        <translation>Plasma en a besoin pour démarrer ; il reste activé</translation>
    </message>
    <message>
        <location filename="../../grimoire/spells/systeml/system.py"/>
        <source>only your own startup entries can be removed</source>
        <translation>seules vos propres entrées de démarrage peuvent être retirées</translation>
    </message>
    <message>
        <source>Couldn&apos;t read the log.</source>
        <translation type="vanished">Impossible de lire le journal.</translation>
    </message>
    <message>
        <source>No log lines yet.</source>
        <translation type="vanished">Le journal est encore vide.</translation>
    </message>
    <message>
        <source>USB drive</source>
        <translation type="vanished">Clé ou disque USB</translation>
    </message>
    <message>
        <source>Hard drive</source>
        <translation type="vanished">Disque dur</translation>
    </message>
    <message>
        <source>couldn&apos;t unmount</source>
        <translation type="vanished">impossible de démonter</translation>
    </message>
</context>
</TS>
