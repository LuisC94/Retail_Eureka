import pandas as pd
import numpy as np
import math
import os
from sklearn.preprocessing import MinMaxScaler

class PricingStockEnvironment:
    """
    OpenAI Gym-style Environment for Pricing and Stock Depletion.
    Simulates selling fresh fruits under price elasticity of demand and biological decay.
    State representation is upgraded to 17 dimensions to mirror the Buyer Agent complexity.
    Actions:
      - Price Multiplier (0.5 to 1.5 of the baseline price)
      - Quantity Percent to Put on Shelf (0.0 to 1.0 of the current warehouse stock)
    """
    
    PRESETS = {
        "kiwi_hayward": {
            "label": "Kiwi (Hayward)",
            "Tref_C": 5.0, "Ea_J": 60000.0, "k_firm_ref": 0.06, "alpha_E": 1.8,
            "beta_RH": 1.2, "RH_ref": 90.0,
            "dureza_min": 3.0, "dureza_0_default": 45.0,
            "brix_min": 11.0, "brix_max": 17.0, "brix_g": 0.35, "brix_0_default": 11.0,
            "qual_firm_threshold": 8.0, "qual_brix_target": 15.0,
            "E0_int": 0.02, "Eref_prod": 0.12, "E_t0": 10.0, "E_g": 0.9, "E_auto": 0.35,
            "E_decay": 0.7, "Ea_E_J": 52000.0, "E_ext_shift": 2.0,
            "elasticity": 1.5
        },
        "maca_golden": {
            "label": "Maçã (Golden)",
            "Tref_C": 5.0, "Ea_J": 50000.0, "k_firm_ref": 0.025, "alpha_E": 0.8,
            "beta_RH": 0.8, "RH_ref": 90.0,
            "dureza_min": 12.0, "dureza_0_default": 72.0,
            "brix_min": 11.5, "brix_max": 15.5, "brix_g": 0.18, "brix_0_default": 12.0,
            "qual_firm_threshold": 35.0, "qual_brix_target": 13.5,
            "E0_int": 0.01, "Eref_prod": 0.1, "E_t0": 18.0, "E_g": 0.6, "E_auto": 0.35,
            "E_decay": 0.55, "Ea_E_J": 52000.0, "E_ext_shift": 1.8,
            "elasticity": 1.4
        },
        "maca_reineta": {
            "label": "Maçã (Reineta)",
            "Tref_C": 5.0, "Ea_J": 52000.0, "k_firm_ref": 0.035, "alpha_E": 1.1,
            "beta_RH": 1.0, "RH_ref": 90.0,
            "dureza_min": 10.0, "dureza_0_default": 65.0,
            "brix_min": 11.0, "brix_max": 14.0, "brix_g": 0.16, "brix_0_default": 11.5,
            "qual_firm_threshold": 30.0, "qual_brix_target": 12.5,
            "E0_int": 0.01, "Eref_prod": 0.13, "E_t0": 14.0, "E_g": 0.7, "E_auto": 0.40,
            "E_decay": 0.6, "Ea_E_J": 52000.0, "E_ext_shift": 2.0,
            "elasticity": 1.3
        },
        "maca_gala": {
            "label": "Maçã (Gala)",
            "Tref_C": 5.0, "Ea_J": 48000.0, "k_firm_ref": 0.04, "alpha_E": 1.3,
            "beta_RH": 0.9, "RH_ref": 90.0,
            "dureza_min": 9.0, "dureza_0_default": 60.0,
            "brix_min": 12.5, "brix_max": 17.0, "brix_g": 0.25, "brix_0_default": 13.0,
            "qual_firm_threshold": 28.0, "qual_brix_target": 14.5,
            "E0_int": 0.015, "Eref_prod": 0.18, "E_t0": 10.0, "E_g": 0.9, "E_auto": 0.5,
            "E_decay": 0.65, "Ea_E_J": 52000.0, "E_ext_shift": 2.2,
            "elasticity": 1.6
        },
        "maca_fuji": {
            "label": "Maçã (Fuji)",
            "Tref_C": 5.0, "Ea_J": 47000.0, "k_firm_ref": 0.018, "alpha_E": 0.6,
            "beta_RH": 0.7, "RH_ref": 90.0,
            "dureza_min": 15.0, "dureza_0_default": 80.0,
            "brix_min": 13.0, "brix_max": 19.0, "brix_g": 0.15, "brix_0_default": 14.0,
            "qual_firm_threshold": 40.0, "qual_brix_target": 16.0,
            "E0_int": 0.008, "Eref_prod": 0.06, "E_t0": 25.0, "E_g": 0.5, "E_auto": 0.25,
            "E_decay": 0.45, "Ea_E_J": 52000.0, "E_ext_shift": 1.4,
            "elasticity": 1.5
        }
    }

    def __init__(self, excel_path, is_training=True, train_split=0.6, max_capacity=500):
        # 1. Load Data
        self.df = pd.read_excel(excel_path)
        
        # 2. Train/Test Split
        split_index = int(len(self.df) * train_split)
        if is_training:
            self.data = self.df.iloc[:split_index].reset_index(drop=True)
        else:
            self.data = self.df.iloc[split_index:].reset_index(drop=True)
            
        self.max_steps = len(self.data) - 1
        self.current_step = 0
        self.max_capacity = max_capacity
        
        # Determine SKU key
        excel_name = os.path.basename(excel_path).lower()
        if "3_080" in excel_name:
            self.fruit_key = "maca_gala"
        elif "3_090" in excel_name:
            self.fruit_key = "maca_fuji"
        elif "3_252" in excel_name:
            self.fruit_key = "kiwi_hayward"
        elif "3_586" in excel_name or "2_586" in excel_name:
            self.fruit_key = "maca_golden"
        elif "911753" in excel_name:
            self.fruit_key = "maca_reineta"
        else:
            self.fruit_key = "maca_gala"
            
        # Get preset parameters
        self.p = self.PRESETS[self.fruit_key]
        try:
            from django.apps import apps
            if apps.ready:
                from dashboard.models import ProductSubFamily
                search_name = "Gala"
                if self.fruit_key == "kiwi_hayward":
                    search_name = "Hayward"
                elif self.fruit_key == "maca_golden":
                    search_name = "Gold"
                elif self.fruit_key == "maca_fuji":
                    search_name = "Fuji"
                elif self.fruit_key == "maca_reineta":
                    search_name = "Reineta"
                
                subfamily = ProductSubFamily.objects.filter(name__icontains=search_name).first()
                if subfamily and subfamily.lifecycle_presets:
                    merged_p = dict(self.PRESETS[self.fruit_key])
                    # Convert key names to types correctly if stored as string in JSON
                    for k, v in subfamily.lifecycle_presets.items():
                        merged_p[k] = v
                    self.p = merged_p
                    print(f"[PricingStockEnv] Coeficientes biológicos de {self.fruit_key} carregados com sucesso da base de dados.")
        except Exception:
            pass

        self.elasticity = self.p["elasticity"]
        
        # Economics constants
        self.product_volume_m3 = self.data['volume'].iloc[0] if 'volume' in self.data.columns else 0.002
        self.CUSTO_ARMAZEM_POR_M3 = 0.70  # Cost per m3 of stock per day
        
        # Tracking variables
        self.active_batches = []
        self.stock_profile = [0.0, 0.0, 0.0, 0.0] # [G0, G1, G2, G3]
        self.sales_history = []
        
        # MinMaxScaler for normalizing the first 9 absolute dimensions of the state vector
        self.scaler = MinMaxScaler()
        min_array = [0.0] * 9
        # Bounding limits: G0..G4, total_stock, pred_t, pred_t+1, sales_t-1, sales_t-2
        max_array = [float(self.max_capacity)] * 5 + [200.0] * 4
        self.scaler.fit(np.array([min_array, max_array]))

    def reset(self):
        self.current_step = 0
        self.sales_history = []
        # Initialize warehouse with 100 boxes of quality 100.0 at day 0
        self.active_batches = [{
            'quantity': 100.0,
            'dureza': float(self.p["dureza_0_default"]),
            'brix': float(self.p["brix_0_default"]),
            'mold': 0.0,
            'E_int': float(self.p.get("E0_int", 0.01)),
            'age': 0.0,
            'quality': 100.0
        }]
        self._refresh_batch_rsls()
        self._update_stock_profile()
        return self._get_state()

    def advance_batch_one_day(self, batch, T_c, RH_pct, E_ext_ppm):
        """ Maturation model matching standard decay physics """
        R = 8.314
        dt = 0.1
        steps = int(1.0 / dt)
        
        T_K = T_c + 273.15
        Tref_K = self.p["Tref_C"] + 273.15
        
        def k_temp_scaling(Ea, T, Tref):
            return math.exp((-Ea / R) * (1.0 / T - 1.0 / Tref))
            
        def sigmoid(x):
            return 1.0 / (1.0 + math.exp(-x))
            
        kT_firm = self.p["k_firm_ref"] * k_temp_scaling(self.p["Ea_J"], T_K, Tref_K)
        
        RH_ref = self.p["RH_ref"]
        RH_deficit = max(0.0, (RH_ref - RH_pct) / 100.0)
        kRH = 1.0 + self.p["beta_RH"] * RH_deficit
        
        Ea_E_J = 52000.0
        Eref_prod = self.p.get("Eref_prod", 0.08)
        E_decay = self.p.get("E_decay", 0.7)
        E_t0 = self.p.get("E_t0", 10.0)
        E_g = self.p.get("E_g", 0.9)
        E_auto = self.p.get("E_auto", 0.35)
        E_ext_shift = self.p.get("E_ext_shift", 2.0)
        
        t0_eff = E_t0 - E_ext_shift * math.log1p(max(0.0, E_ext_ppm))
        prod_T = k_temp_scaling(Ea_E_J, T_K, Tref_K)
        
        dureza_min = float(self.p["dureza_min"])
        alpha_E = float(self.p["alpha_E"])
        
        brix_min = float(self.p["brix_min"])
        brix_max = float(self.p["brix_max"])
        r0 = float(self.p["brix_g"])
        alpha_bE = 0.25
        bRH = max(0.0, (RH_ref - RH_pct) / 100.0)
        rRH = 1.0 - 0.6 * bRH
        rT = k_temp_scaling(Ea_E_J, T_K, Tref_K)
        
        dureza = batch['dureza']
        brix = batch['brix']
        mold = batch['mold']
        E_int = batch.get('E_int', float(self.p.get("E0_int", 0.01)))
        age = batch.get('age', 0.0)
        
        for _ in range(steps):
            current_age = age + (_ * dt)
            ramp = sigmoid(E_g * (current_age - t0_eff))
            prod = Eref_prod * prod_T * ramp
            dE = (prod * (1.0 + E_auto * E_int) - E_decay * E_int) * dt
            E_int = max(0.0, E_int + dE)
            
            E_total = E_ext_ppm + E_int
            kE = 1.0 + alpha_E * E_total
            k = kT_firm * kRH * kE
            dD = (-k * (dureza - dureza_min)) * dt
            dureza = max(dureza_min, dureza + dD)
            
            r = r0 * rT * rRH * (1.0 + alpha_bE * E_total)
            x = max(0.0, brix - brix_min)
            K = max(1e-6, brix_max - brix_min)
            db = (r * x * (1.0 - x / K)) * dt
            brix = min(brix_max, max(brix_min, brix + db))
            
        firm_score = 1.0 / (1.0 + math.exp(-0.35 * (dureza - float(self.p["qual_firm_threshold"]))))
        brix_score = math.exp(-((brix - float(self.p["qual_brix_target"]))**2) / 2.0)
        quality = 100.0 * (0.65 * firm_score + 0.35 * brix_score)
        
        return {
            'quantity': batch['quantity'],
            'dureza': dureza,
            'brix': brix,
            'mold': mold,
            'E_int': E_int,
            'age': age + 1.0,
            'quality': quality
        }

    def project_batch_rsl(self, batch):
        b = dict(batch)
        row = self.data.iloc[self.current_step]
        T_c = row['temperature'] if 'temperature' in row else 18.0
        RH_pct = row['humidity'] if 'humidity' in row else 72.0
        E_ext_ppm = row['ethylene'] if 'ethylene' in row else 0.15
        
        days_remaining = 0
        max_projection_days = 60
        
        while days_remaining < max_projection_days:
            if b['quality'] < 30.0:
                break
            b = self.advance_batch_one_day(b, T_c, RH_pct, E_ext_ppm)
            days_remaining += 1
            
        return days_remaining

    def _refresh_batch_rsls(self):
        for b in self.active_batches:
            if b['quantity'] > 0:
                b['rsl'] = self.project_batch_rsl(b)
            else:
                b['rsl'] = 0

    def _update_stock_profile(self):
        self.stock_profile = [0.0, 0.0, 0.0, 0.0]
        for b in self.active_batches:
            if b['quantity'] <= 0:
                continue
            rsl = b.get('rsl', 0)
            if rsl >= 4:
                self.stock_profile[0] += b['quantity']
            elif rsl == 3:
                self.stock_profile[1] += b['quantity']
            elif rsl == 2:
                self.stock_profile[2] += b['quantity']
            elif rsl == 1:
                self.stock_profile[3] += b['quantity']

    def _get_state(self):
        """ Returns the 17-dimensional observation state vector """
        row = self.data.iloc[self.current_step]
        prediction_today = row['prediction']
        price_today = row['price'] if 'price' in row else 2.0
        
        if self.current_step < self.max_steps:
            prediction_tomorrow = self.data.iloc[self.current_step + 1]['prediction']
        else:
            prediction_tomorrow = prediction_today
            
        total_stock = sum(self.stock_profile)
        
        # Lags of actual sales realized
        real_t_minus_1 = self.sales_history[-1] if len(self.sales_history) >= 1 else prediction_today
        real_t_minus_2 = self.sales_history[-2] if len(self.sales_history) >= 2 else real_t_minus_1
        
        # Absolute scaled values
        via1_absolutes = [
            self.stock_profile[0],
            self.stock_profile[1],
            self.stock_profile[2],
            self.stock_profile[3],
            total_stock,
            prediction_today,
            prediction_tomorrow,
            real_t_minus_1,
            real_t_minus_2
        ]
        scaled_via1 = self.scaler.transform([via1_absolutes])[0]
        
        # Relative price Z-score over the last 15 days baseline
        window_prices = []
        for i in range(15):
            idx = max(0, self.current_step - i)
            p = self.data.iloc[idx]['price'] if 'price' in self.data.columns else 2.0
            window_prices.append(p)
        media_15dias = np.mean(window_prices)
        std_15dias = np.std(window_prices)
        preco_relativo = (price_today - media_15dias) / (std_15dias + 1e-8)
        preco_relativo_safe = np.clip(preco_relativo, -3.0, 3.0)
        
        # Calendar cyclical signals
        day_of_year = (self.current_step % 365) + 1
        day_of_week = (self.current_step % 7) + 1
        month = min(12, int((day_of_year / 30.416) + 1))
        
        sin_day = math.sin(2 * math.pi * day_of_week / 7.0)
        cos_day = math.cos(2 * math.pi * day_of_week / 7.0)
        sin_month = math.sin(2 * math.pi * month / 12.0)
        cos_month = math.cos(2 * math.pi * month / 12.0)
        
        # Advanced logistics descriptors
        cobertura_dias = total_stock / (prediction_today + 1e-8)
        cobertura_norm = np.clip(cobertura_dias, 0, 7) / 7.0
        
        urgencia_norm = self.stock_profile[3] / (total_stock + 1e-8)
        
        # Forecast error lag
        if self.current_step >= 1:
            prediction_yesterday = self.data.iloc[self.current_step - 1]['prediction']
            erro_previsao = (real_t_minus_1 - prediction_yesterday) / (prediction_yesterday + 1e-8)
        else:
            erro_previsao = 0.0
        erro_norm = np.clip(erro_previsao, -1.0, 1.0)
        
        via2_bypass = [
            preco_relativo_safe,
            sin_day,
            cos_day,
            sin_month,
            cos_month,
            cobertura_norm,
            urgencia_norm,
            erro_norm
        ]
        
        final_state = np.concatenate([scaled_via1, via2_bypass])
        return final_state

    def step(self, action):
        """
        Executes daily sales and decay loop.
        action: [price_multiplier, quantity_percent]
        """
        price_mult, qty_pct = action
        price_mult = np.clip(price_mult, 0.5, 1.5)
        qty_pct = np.clip(qty_pct, 0.0, 1.0)
        
        row = self.data.iloc[self.current_step]
        base_price = row['price'] if 'price' in row else 2.0
        base_demand = row['prediction']
        
        # Refresh RSL cache at step start
        self._refresh_batch_rsls()
        
        # 1. Price Elasticity of Demand Math
        elastic_demand = base_demand * (price_mult ** (-self.elasticity))
        
        # 2. Limit sales by shelf-exposure and warehouse stock
        total_stock_before = sum(b['quantity'] for b in self.active_batches if b['quantity'] > 0)
        max_exposed_qty = total_stock_before * qty_pct
        
        target_sales = min(elastic_demand, max_exposed_qty)
        
        # 3. FEFO Stock consumption
        self.active_batches.sort(key=lambda b: b.get('rsl', 0))
        remaining_sales_to_satisfy = target_sales
        sales_realized = 0.0
        
        for b in self.active_batches:
            if b['quantity'] <= 0:
                continue
            take = min(b['quantity'], remaining_sales_to_satisfy)
            b['quantity'] -= take
            sales_realized += take
            remaining_sales_to_satisfy -= take
            if remaining_sales_to_satisfy <= 0:
                break
                
        # Record sales history
        self.sales_history.append(sales_realized)
        
        # 4. Supply Inflow (Replenishment)
        # Steady supply stream arriving fresh daily
        inflow_qty = base_demand
        total_stock_after_sales = sum(b['quantity'] for b in self.active_batches if b['quantity'] > 0)
        
        accepted_inflow = min(inflow_qty, self.max_capacity - total_stock_after_sales)
        if accepted_inflow > 0:
            self.active_batches.append({
                'quantity': float(accepted_inflow),
                'dureza': float(self.p["dureza_0_default"]),
                'brix': float(self.p["brix_0_default"]),
                'mold': 0.0,
                'E_int': float(self.p.get("E0_int", 0.01)),
                'age': 0.0,
                'quality': 100.0
            })
            
        # 5. Biological Aging and Spoilage for all active batches
        T_c = row['temperature'] if 'temperature' in row else 18.0
        RH_pct = row['humidity'] if 'humidity' in row else 72.0
        E_ext_ppm = row['ethylene'] if 'ethylene' in row else 0.15
        
        spoilage = 0.0
        updated_batches = []
        for b in self.active_batches:
            if b['quantity'] <= 0:
                continue
            b_next = self.advance_batch_one_day(b, T_c, RH_pct, E_ext_ppm)
            if b_next['quality'] < 30.0:
                spoilage += b_next['quantity']
            else:
                updated_batches.append(b_next)
                
        self.active_batches = updated_batches
        self._update_stock_profile()
        
        # 6. Financial Calculations & Rewards
        cogs = base_price * 0.60
        actual_price = base_price * price_mult
        
        revenue = sales_realized * actual_price
        cost_of_sales = sales_realized * cogs
        
        final_stock = sum(b['quantity'] for b in self.active_batches)
        volume_stock_final = final_stock * self.product_volume_m3
        storage_cost = volume_stock_final * self.CUSTO_ARMAZEM_POR_M3
        
        spoilage_cost = spoilage * cogs
        
        daily_profit = revenue - cost_of_sales - storage_cost - spoilage_cost
        
        # Regularization penalty to avoid extreme deviations from default pricing and exposition
        price_penalty = 5.0 * ((price_mult - 1.0) ** 2)
        qty_penalty = 5.0 * ((1.0 - qty_pct) ** 2)
        
        # Scaled reward to guide gradient updates
        reward = (daily_profit / 100.0) - price_penalty - qty_penalty
        
        self.current_step += 1
        done = self.current_step >= self.max_steps
        
        next_state = self._get_state() if not done else np.zeros(17, dtype=np.float32)
        
        info = {
            'sales': sales_realized,
            'price_multiplier': price_mult,
            'quantity_percent': qty_pct,
            'demand_expected': base_demand,
            'elastic_demand': elastic_demand,
            'spoilage': spoilage,
            'profit': daily_profit,
            'revenue': revenue,
            'final_stock': final_stock
        }
        
        return next_state, reward, done, info

    def get_checkpoint(self):
        """ Returns a copy of the current state variables to allow for lookahead simulations """
        return {
            'current_step': self.current_step,
            'stock_profile': list(self.stock_profile),
            'sales_history': list(self.sales_history),
            'active_batches': [dict(b) for b in self.active_batches]
        }

    def load_checkpoint(self, checkpoint):
        """ Restores environment from a saved checkpoint """
        self.current_step = checkpoint['current_step']
        self.stock_profile = list(checkpoint['stock_profile'])
        self.sales_history = list(checkpoint['sales_history'])
        self.active_batches = [dict(b) for b in checkpoint['active_batches']]
