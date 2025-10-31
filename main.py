from gurobipy import GRB, Model, quicksum
from datos import vientos

# Instanciar Parametros
c_t_w = 1           # Costo de comprar agua en el periodo t [$/L] 
r_t_b = 120000      # Costo de comprar energía de la red en el periodo t [$/MWh]
r_t_s = 50000       # Precio de venta de energía eólica a la red en el periodo t [$/MWh]
Emax_m_t = 90       # Energía máxima que puede entregar la turbina m en el periodo t [MWh]
alpha = 130000      # Costo de mantenimiento de la turbina m en el periodo t [$]
v_mt = vientos      # Velocidad de la turbina m en el dia t
v_max = 90          # Velocidad máxima del viento permitida [km/h]
v_min = 12.6        # Velocidad mínima del viento para funcionamiento [km/h]
d_T = 718000        # Demanda mínima de producción de H2 al final del horizonte [kg]
n_MW = 0.05         # Proporción de conversión de electricidad a H2 [MWh/kg]
n_H2O = 15          # Proporción de conversión de agua a H2 [L/kg]
n_bat = 0.00015     # Perdida de energía de la batería por periodo [%]
Bmax = 600          # Capacidad máxima de almacenamiento de energía en la batería [MWh]
H_max = 530         # Capacidad máxima de producción de hidrógeno por electrolizador [kg]

# Rangos de Conjuntos
DIAS_HORIZONTE = 365
TURBINAS_DISPONIBLES = 4
ELECTROLIZADORES_DISPONIBLES = 4

# Crear conjuntos
T = range(DIAS_HORIZONTE) #t Lo dejamos como 365 y no (1, 366) porque o si no sale index out of range
M = range(TURBINAS_DISPONIBLES) #m
N = range(ELECTROLIZADORES_DISPONIBLES) #n

# preiniciar el viento para que no lo cambie
A_mt = {}
for m in M:
 for t in T:
   viento = v_mt[m,t]
   if v_min <= viento <= v_max:
       A_mt[m, t] = 1
   else:
       A_mt[m, t] = 0

# Crear modelo
model = Model("HaruOni")
model.setParam("TimeLimit", 1800)

# Instanciar variables
e_t_buy = model.addVars(T, vtype=GRB.CONTINUOUS, lb=0, name="e_t^buy")
e_t_sell = model.addVars(T, vtype=GRB.CONTINUOUS, lb=0, name="e_t^sell")
b_t_carga = model.addVars(T, vtype=GRB.CONTINUOUS, lb=0, name="b_t^carga")
b_t_cons = model.addVars(T, vtype=GRB.CONTINUOUS, lb=0, name="b_t^cons")
a_t = model.addVars(T, vtype=GRB.CONTINUOUS, lb=0, name="a_t")
u_nt = model.addVars(N, T, vtype=GRB.CONTINUOUS, lb=0, name="u_nt")
h_nt = model.addVars(N, T, vtype=GRB.CONTINUOUS, lb=0, name="h_nt")
E_mt = model.addVars(M, T, vtype=GRB.CONTINUOUS, lb=0, name="E_mt")
w_nt = model.addVars(N, T, vtype=GRB.CONTINUOUS, lb=0, name="w_nt")
k_mt = model.addVars(M, T, vtype=GRB.BINARY, name="k_mt")

model.update()

# Restricciones

# (1) y (2) Prendido de la turbina
model.addConstrs((k_mt[m,t] <= A_mt[m,t] for t in T for m in M), name="R1_R2")

# (1) Prendido de la turbina (para cada periodo t) (vmax)
#model.addConstrs((k_mt[m,t]*v_mt[m,t] <= k_mt[m,t]*v_max for t in T for m in M), name="R1")

# (2) Prendido de la turbina (para cada periodo t) (vmin)
#model.addConstrs((k_mt[m,t]*v_mt[m,t] >= k_mt[m,t]*v_min for t in T for m in M), name="R2")

# (3) Estado de la turbina (para cada periodo t)
model.addConstrs((Emax_m_t*k_mt[m,t] >= E_mt[m,t] for t in T for m in M), name="R3")

# (4) Balance de Energia
model.addConstrs((quicksum(E_mt[m,t] for m in M) + e_t_buy[t] + b_t_cons[t] == quicksum(u_nt[n,t] for n in N) + e_t_sell[t] + b_t_carga[t] for t in T), name="R4")

# (5) Balance de la Bateria
model.addConstrs(((1 - n_bat) * a_t[t-1] + b_t_carga[t] - b_t_cons[t] == a_t[t] for t in T if t > 0), name="R5")

# (6) Condicion Inicial
model.addConstr((b_t_carga[0] - b_t_cons[0] == a_t[0]), name="R6")

# (7) Capacidad de la Bateria
model.addConstrs((a_t[t] <= Bmax for t in T), name="R7")

# (8) Meta de produccion de hidrogeno
model.addConstr((quicksum(h_nt[n,t] for n in N for t in T) >= d_T), name="R8")

# (9) Produccion de Hidrogeno
model.addConstrs((h_nt[n,t] == u_nt[n,t]/n_MW for t in T for n in N), name="R9a")
model.addConstrs((h_nt[n,t] == w_nt[n,t]/n_H2O for t in T for n in N), name="R9b")

# (10) Balance neto de energia verde
model.addConstr((quicksum(e_t_sell[t] - e_t_buy[t] for t in T) >= 0), name="R10")

# (11) Capacidad de electrolizadores
model.addConstrs((h_nt[n,t] <= H_max for t in T for n in N), name="R11")

# (12) No negatividad
model.addConstrs((e_t_buy[t] >= 0 for t in T), name="R12a")
model.addConstrs((e_t_sell[t] >= 0 for t in T), name="R12b")
model.addConstrs((E_mt[m, t] >= 0 for m in M for t in T), name="R12c")
model.addConstrs((u_nt[n, t] >= 0 for n in N for t in T), name="R12d")
model.addConstrs((b_t_carga[t] >= 0 for t in T), name="R12e")
model.addConstrs((b_t_cons[t] >= 0 for t in T), name="R12f")
model.addConstrs((h_nt[n, t] >= 0 for n in N for t in T), name="R12g")
model.addConstrs((a_t[t] >= 0 for t in T), name="R12h")
model.addConstrs((w_nt[n, t] >= 0 for n in N for t in T), name="R12i")

# Funcion Objetivo
objetivo = quicksum(quicksum(k_mt[m,t]*alpha for m in M) + quicksum(w_nt[n,t]*c_t_w for n in N) + e_t_buy[t]*r_t_b - e_t_sell[t]*r_t_s for t in T)

model.setObjective(objetivo, GRB.MINIMIZE)

# Opotimizar
model.optimize()

if model.status == GRB.OPTIMAL:
     print("\nRESULTADOS")

     # Costo optimo
     print(f"\nCosto optimo: ${model.objVal:,.2f}")

     # Energia comprada y vendida
     energia_comprada = sum(e_t_buy[t].X for t in T)
     energia_vendida  = sum(e_t_sell[t].X for t in T)
     print(f"\nEnergia total comprada: {energia_comprada:.2f} MWh")
     print(f"Energia total vendida:  {energia_vendida:.2f} MWh")
     print(f"Balance neto de energia: {energia_vendida - energia_comprada:.2f} MWh")

     # Producion de hidrogeno
     produccion_hidrogeno = sum(h_nt[n,t].X for n in N for t in T)
     print(f"\nProduccion total de Hidrogeno verde: {produccion_hidrogeno:.2f} kg")


     # Promedios
     print("\nPromedios diarios:")
     print(f"Energia comprada promedio: {energia_comprada/len(T):.3f} MWh/dia")
     print(f"Energia vendida promedio:  {energia_vendida/len(T):.3f} MWh/dia")
     print(f"Hidrogeno producido promedio: {produccion_hidrogeno/len(T):.3f} kg/dia")

     # Generacion por turbina
     print("\nTurbinas:")
     for m in M:
          energia_m = sum(E_mt[m,t].X for t in T)
          print(f"Generacion de Turbina {m}: {energia_m:.2f}")

     print("\nElectrolizadores")
     for n in N:
          h2_n = sum(h_nt[n,t].X for t in T)
          print(f"Produccion de hidrogeno de electrolizador {n}: {h2_n:.2f} kg de hidrogeno")

else:
     print("\nNo se encontró solución óptima.")