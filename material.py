from sqlite import make_simple as sql

single_wall_flute = ['B','C', 'E']
ect = {23:[(1500,4999, 88.6),(1500,4999, 88.6)], 
                   26:[(1500,4999, 88.6),(1500,4999, 88.6)],
                   29:[(1500,4999, 88.6),(1500,4999, 88.6)],
                   32:[(1500,4999, 88.6),(1500,4999, 88.6)],
                   40:[(1500,4999, 88.6),(1500,4999, 88.6)],
                   44:[(1500,4999, 88.6),(1500,4999, 88.6)],}

list_prices = []
#addinng adder
str_adder = f"""Coated White,Coated White 2 sides,Oyster,Oyster 2 sides,Kraft,Rod Coated,Rod Coated 2 sides,MRA Single Wall,WRA Single Wall,30# Medium,36# Medium"""
list_adder = str_adder.split(",")

adder_prices = [0,0,0,0,0,0,0,0,0,0,0]

zipped = dict(zip(list_adder, adder_prices))
# print(zipped)

# for i in list_adder:
#     e = i
#     material_id = sql().get_material(i)
#     vendor_id = sql().get_supplier('Master')
#     if material_id and vendor_id:
#         min, max = [0,999999]
#         if i == "Oyster":
#             i = "Whitetop"
#         elif i == "Oyster 2 sides":
#             i = "Whitetop 2 sides"
#         list_prices.append((vendor_id,material_id,i,"Adder",min,max,zipped[e]))

# print(list_prices)
# sql().insert_multiple_price(list_prices)

# for i in single_wall_flute:
#     for k, v in ect.items():
#         for l in v:
#             print(l[0])

#Master
min = "15000 TO 25000 TO 50000".split(" TO ")
max = "24999 49999 999999".split(' ')
test = list(zip(min,max))

pricing = "19.79 18.81 21.19".split(' ') # adder clay
# pricing = '99.29 97.7 93.12'.split(' ') #ect 40B

#Green
# min = "0 TO 50000 TO 100000".split(" TO ")
# max = "49999 99999 999999".split(' ')
# test = list(zip(min,max))

# pricing = '46.25 46.01 45.77'.split(' ')
# pricing = '49.56 49.30 49.04'.split(' ')
# pricing = '51.60 51.33 51.06'.split(' ')
# pricing = '57.51 57.21 56.90'.split(' ')
# pricing = '63.48 63.14 62.81'.split(' ')
# pricing = '88.19 87.72 87.27'.split(' ')

#Coastal
# min = "3000 10000 25000 50000 75000 10000".split(" ")
# max = "9999 24999 49999 74999 99999 999999".split(' ')
# test = list(zip(min,max))
# pricing = '69.43 60.09 58.02 58.02 57.01 56.03'.split(' ') #32
# pricing = '76.59 65.87 64.70 63.57 62.44 61.35'.split(' ') #40
# pricing = '87.82 75.43 74.08 72.75 71.45 70.18'.split(' ') #44
# pricing = '84.77 72.28 71.00 69.74 68.51 67.29'.split(' ') #200
# pricing = '121.11 102.87 100.99 99.13 97.32 95.55'.split(' ') #275

# maybe = dict(zip(pricing,test))
# for flute in ["40B", "40C"]:
#     for price, v in maybe.items():
#         min, max = v
        # print(f'flute: {flute},min:{min}, max:{max}, price:{price}')

# min = "15000 TO 25000 TO 50000".split(" TO ")
# max = "24999 49999 999999".split(' ')
maybe = dict(zip(pricing,test))

# prices = []
# prices.append('145.26 132.18 130.00 128.59 127.44'.split(' '))
# prices.append('150.88 137.30 135.51 133.73 132.57'.split(' '))
# prices.append('156.09 142.03 140.23 138.94 137.91'.split(' '))
# prices.append('172.94 157.36 155.24 153.77 153.00'.split(' '))
# prices.append('182.16 165.77 163.36 161.72 160.11'.split(' '))
# prices.append('197.33 179.58 176.95 175.18 173.44'.split(' '))
# prices.append('210.27 191.35 188.53 186.66 184.80'.split(' '))

# maybe = dict(zip(prices[6],test))



ect = "40"
flutes = []
for i in ["C"]:
    flutes.append(f'{ect+i}')

for flute in flutes:
    material_id = sql().get_material("Coated White")
    vendor_id = sql().get_supplier_id('Master')
    if material_id and vendor_id:
        for price, v in maybe.items():
            min, max = v
            list_prices.append((vendor_id,material_id,"Clay","Adder",min,max,price))

# print(list_prices)
# print()
sql().insert_multiple_price(list_prices)