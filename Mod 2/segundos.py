sec = None
while type(sec) != int:
    sec =  input("Por favor, entre com o número de segundos que deseja converter: ")
    try:
        sec = int(sec)
    except ValueError:
        print("Entrada inválida. Por favor, digite um número inteiro.")
horas = sec // 3600
segundos = sec % 3600
minutos = segundos // 60
dias = horas // 24
print(f"{dias} dias, {horas % 24} horas, {minutos} minutos e {segundos % 60} segundos.")
