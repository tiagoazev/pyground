input_user = None
lado = None
while type(lado) != float:
    input_user = input("Qual o tamanho do lado do quadrado? ")
    try: 
        lado = float(input_user)
    except ValueError:
        if input_user == "e":
            exit()
        print("Por favor, insira um número válido. Ou digite 'e' para sair.")
perimetro = lado * 4
area = lado * lado
print(f"perímetro: {perimetro:g} - área: {area:g}")