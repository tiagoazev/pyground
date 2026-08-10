nome_cliente = ""
dia_venc = 0
mes_venc = 0
valor_fatura = 0.0


nome_cliente = input("Digite o nome do cliente: ")
dia_venc = input("Digite o dia de vencimento: ")
mes_venc = input("Digite o mês de vencimento: ")
valor_fatura = input("Digite o valor da fatura: ")    
print(f"Olá, {nome_cliente}")
print(f"A sua fatura com vencimento em {dia_venc} de {mes_venc} no valor de R$ {valor_fatura} está fechada.")