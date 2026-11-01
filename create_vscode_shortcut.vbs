
Set WshShell = CreateObject("WScript.Shell")

' Atalho 1: Abrir Projeto no VS Code
Set shortcutVS = WshShell.CreateShortcut("C:\Users\user\Desktop\VS Code - TCC Cafe Arara.lnk")
shortcutVS.TargetPath = "C:\Users\user\AppData\Local\Programs\Microsoft VS Code\Code.exe"
shortcutVS.Arguments = '"C:\Users\user\.gemini\antigravity\scratch\tcc-cafe-arara"'
shortcutVS.WorkingDirectory = "C:\Users\user\.gemini\antigravity\scratch\tcc-cafe-arara"
shortcutVS.Description = "Abrir projeto TCC Cafe Arara no Visual Studio Code"
shortcutVS.IconLocation = "C:\Users\user\AppData\Local\Programs\Microsoft VS Code\Code.exe,0"
shortcutVS.Save

' Atalho 2: Pasta Codigo Fonte
Set shortcutFolder = WshShell.CreateShortcut("C:\Users\user\Desktop\Pasta Codigo Fonte - TCC Cafe Arara.lnk")
shortcutFolder.TargetPath = "explorer.exe"
shortcutFolder.Arguments = "C:\Users\user\.gemini\antigravity\scratch\tcc-cafe-arara"
shortcutFolder.WorkingDirectory = "C:\Users\user\.gemini\antigravity\scratch\tcc-cafe-arara"
shortcutFolder.Description = "Pasta do projeto TCC Cafe Arara"
shortcutFolder.Save
