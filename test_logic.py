import logic
import traceback

def test():
    try:
        print("Testing initial")
        payload = logic.analyze_interaction("", logic.DEFAULT_USER_ID)
        print("Initial OK")

        print("Testing onboarding")
        payload = logic.analyze_interaction("inicio", logic.DEFAULT_USER_ID)
        print("Onboarding OK")

        print("Testing card request")
        payload = logic.analyze_interaction("solicitar tarjeta física", logic.DEFAULT_USER_ID)
        print("Card 1 OK")
        
        payload = logic.analyze_interaction("ya estoy en tarjeta", logic.DEFAULT_USER_ID)
        print("Card 2 OK")

        payload = logic.analyze_interaction("sí, enviar a este domicilio", logic.DEFAULT_USER_ID)
        print("Card 3 OK")

        print("Testing finanzas")
        payload = logic.analyze_interaction("gastos", logic.DEFAULT_USER_ID)
        print("Finanzas OK")
    except Exception as e:
        print("CRASHED!")
        traceback.print_exc()

test()
