# Record with: vhs docs/assets/demo.tape (needs cloud-audit on PATH)
# Fake data only. A throwaway HOME and a bare prompt keep local details out of the recording.
Output docs/assets/demo.gif
Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 14
Set Width 1200
Set Height 720
Set Theme "Dracula"
Set Padding 24
Set TypingSpeed 35ms

Hide
Type "export HOME=$(mktemp -d) PS1='$ '; clear"
Enter
Sleep 500ms
Show

Type "cloud-audit collect --demo --resource unused"
Enter
Sleep 3s
Type "cloud-audit collect --demo --resource audit_log | head -22"
Enter
Sleep 6s
