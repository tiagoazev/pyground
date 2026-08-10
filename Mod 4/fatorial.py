
n = int(input("Digite o valor de n: "))

while n < 0:
    print("Digite um valor válido!")
    n = int(input("Digite o valor de n: "))

resultado = 1
contador = 1

while contador <= n:
    resultado = resultado * contador
    contador += contador

print(resultado)