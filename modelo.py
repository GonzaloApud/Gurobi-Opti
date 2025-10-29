from gurobipy import GRB, Model, quicksum
import numpy as np

# Algunos parametros deben ser definidos como arreglos np
# Ejemplo:
q = [[10, 20, 10],
     [11, 40, 3 ],
     [12, 30, 5 ],
     [11, 34, 2 ],
     [12, 28, 4 ],
     [11, 22, 8 ],
     [12, 46, 10]]

# Instanciar Parametros (Hay que buscarlos D:)
c_t_w = 1      # Costo de comprar agua en el periodo t [$/L]
r_t_b = 1      # Costo de comprar energía de la red en el periodo t [$/MWh]
r_t_s = 1      # Precio de venta de energía eólica a la red en el periodo t [$/MWh]
Emax_m_t = 1   # Energía máxima que puede entregar la turbina m en el periodo t [MWh]
om_t = 1       # Costo de mantenimiento de la turbina m en el periodo t [$]
v_mt           # Velocidad de la turbina m en el dia t
v_max = 1      # Velocidad máxima del viento permitida [km/h]
v_min = 1      # Velocidad mínima del viento para funcionamiento [km/h]
d_T = 1        # Demanda mínima de producción de H2 al final del horizonte [kg]
n_MW = 0.02  # Eficiencia de conversión de electricidad a H2 [kg/MWh]
n_H2O = 0.0667  # Eficiencia de conversión de agua a H2 [kg/L]
Bmax = 1       # Capacidad máxima de almacenamiento de energía en la batería [MWh]

# Rangos de Conjuntos (Hay que definirlo)
TURBINAS_DISPONIBLES = 1
ELECTROLIZADORES_DISPONIBLES = 1

# Crear conjuntos
T = range(365) #t
M = range(TURBINAS_DISPONIBLES)
N = range(ELECTROLIZADORES_DISPONIBLES)

# Crear modelo
model = Model()
model.setParam("TimeLimit", 120)


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

# (1) Prendido de la turbina (para cada periodo t) (vmax)
model.addConstrs(k_mt[m,t]*v_mt[m,t] <= k_mt[m,t]*v_max for t in T for m in M, name="R1")

# (2) Prendido de la turbina (para cada periodo t) (vmin)
model.addConstrs(k_mt[m,t]*v_mt[m,t] >= k_mt[m,t]*v_min for t in T for m in M, name="R2")

# (3) Estado de la turbina (para cada periodo t)
model.addConstrs(Emax_m_t[m,t]*k_mt[m,t] >= E_mt[m,t] for t in T for m in M, name="R3")

# (4) Balance de Energia
model.addConstrs(quicksum(E_mt[m,t]  for m in M) + e_t_buy[t] + b_t_cons[t] == quicksum(u_nt[n,t] for n in N) + e_t_sell[t] + b_t_carga[t] for t in T, name="R4")

# (5) Balance de la Bateria
model.addConstrs(a_t[t-1] + b_t_carga[t] - b_t_cons[t] == a_t[t] for t in T if t != 0, name="R5")

# (6) Condicion Inicial
model.addConstr(a_t[0] == 0, name="R6")

# (7) Capacidad de la Bateria
model.addConstrs(a_t[t] <= Bmax for t in T, name="R7")

# (8) Meta de produccion de hidrogeno
model.addConstrs((quicksum(h_nt[n,t]) for n in N for t in T) >= d_T[T] for t in T, name="R8")

# (9) Produccion de Hidrogeno
model.addConstrs(h_nt[n,t] <= u_nt[n,t]*n_MW for t in T for n in N, name="R9a")
model.addConstrs(h_nt[n,t] <= w_nt[n,t]*n_H2O for t in T for n in N, name="R9b")

# (10) Balance neto de energia verde
model.addConstrs((quicksum(e_t_sell[t] - e_t_buy[t]) for t in T) >= 0, name="R10")

# (11) No negatividad
model.addConstrs(e_t_buy[t] >= 0 for t in T, name="R11a")
model.addConstrs(e_t_sell[t] >= 0 for t in T, name="R11b")
model.addConstrs(E_mt[m, t] >= 0 for m in M for t in T, name="R11c")
model.addConstrs(u_nt[n, t] >= 0 for n in N for t in T, name="R11d")
model.addConstrs(b_t_carga[t] >= 0 for t in T, name="R11e")
model.addConstrs(b_t_cons[t] >= 0 for t in T, name="R11f")
model.addConstrs(h_n_t[n, t] >= 0 for n in N for t in T, name="R11g")
model.addConstrs(a_t[t] >= 0 for t in T, name="R11h")
model.addConstrs(w_n_t[n, t] >= 0 for n in N for t in T, name="R11i")

# Funcion Objetivo
objetivo = (quicksum(quicksum(k_mt[m,t]*om_t[m,t] for m in M) + quicksum(w_n_t[n,t]*c_t_w[t] for n in N) + e_t_buy[t]*r_t_b[t] - e_t_sell[t]*r_t_s[t] for t in T))
model.setObjective(objetivo, GRB.MINIMIZE)

# Opotimizar
model.optimize()