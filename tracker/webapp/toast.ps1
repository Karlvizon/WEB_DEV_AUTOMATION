# Windows pop-up for the MLP Tracker (user, 2026-11-13: "build it with pop ups").
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File toast.ps1 -Title "..." -Body "..." [-Url "http://127.0.0.1:8765/#revision"]
# Clicking the pop-up opens the tracker page. Uses the built-in Windows notification API (no extra modules).
param([string]$Title = "Web Dev Tracker", [string]$Body = "", [string]$Url = "http://127.0.0.1:8765/",
      [string]$Action2 = "", [string]$Url2 = "")   # optional extra button, e.g. "Fix it now" (user, 2026-11-13)
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
function Esc([string]$s) { [System.Security.SecurityElement]::Escape($s) }
$xml = @"
<toast activationType="protocol" launch="$(Esc $Url)" scenario="default">
  <visual><binding template="ToastGeneric"><text>$(Esc $Title)</text><text>$(Esc $Body)</text></binding></visual>
  <actions>$(if ($Action2 -and $Url2) { "<action content=`"$(Esc $Action2)`" activationType=`"protocol`" arguments=`"$(Esc $Url2)`"/>" })<action content="Open tracker" activationType="protocol" arguments="$(Esc $Url)"/></actions>
</toast>
"@
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
# PowerShell's own app id: always registered, so the pop-up shows without installing anything
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($doc))
