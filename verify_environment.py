import sys
import subprocess

def test_environment():
    try:
        import torch
        import ultralytics
        import streamlit
        print("[OK] Ambiente Python e bibliotecas carregados com sucesso!")
        return 0
    except OSError as e:
        err_msg = str(e)
        if "4551" in err_msg or "Controle de Aplicativo" in err_msg or "blocked" in err_msg.lower():
            print("\n" + "=" * 72)
            print("  [BLOQUEIO DE SEGURANÇA DO WINDOWS 11 IDENTIFICADO]")
            print("=" * 72)
            print("O recurso 'Controle Inteligente de Aplicativos' (Smart App Control) do")
            print("Windows 11 bloqueou os arquivos de IA (PyTorch / c10.dll).")
            print("\nEste recurso do Windows bloqueia qualquer código de Machine Learning")
            print("ou desenvolvimento que não possua assinatura comercial da Microsoft.")
            print("\n>>> COMO RESOLVER AGORA MESMO (Leva 30 segundos):")
            print("1. Na janela de 'Segurança do Windows' que acabou de abrir na sua tela:")
            print("   - Clique em: 'Configurações do Controle Inteligente de Aplicativos'")
            print("   - Altere para: 'Desativado' (ou 'Avaliação')")
            print("\n2. Assim que desativar, aperte ENTER aqui embaixo ou abra o atalho de novo!")
            print("=" * 72 + "\n")
            
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", "windowsdefender://appbrowser"], shell=False)
            except Exception:
                pass
            
            input("Pressione ENTER após desativar o Controle Inteligente para continuar...")
            # Tentar novamente
            try:
                import torch
                print("[SUCESSO] Bloqueio resolvido! Continuando inicialização...")
                return 0
            except Exception:
                print("[AVISO] O bloqueio ainda está ativo. Reinicie o atalho após desativar.")
                return 1
        else:
            print(f"[ERRO AO CARREGAR AMBIENTE]: {e}")
            return 1
    except Exception as e:
        print(f"[AVISO]: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(test_environment())
