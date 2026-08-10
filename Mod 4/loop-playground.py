#imprimir n fatorial
#Dica: lembre-se que o fatorial de 0 vale 1!

while True:
    try:
        n = int(input("Digite um valor de n: "))
        if n < 0:
            print("Digite um valor não negativo.")
            continue
        break
    except ValueError:
        print("Valor inválido! Digite um número inteiro.")
fatorial = 1
for i in range(1, n + 1):
    fatorial *= i
print(f"O fatorial de {n} é {fatorial}")