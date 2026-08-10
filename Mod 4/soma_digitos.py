soma = 0
n = int(input("Digite o valor de n: "))

while n > 0:
    n1 = n % 10
    soma = soma + n1
    n = n // 10

print(soma)