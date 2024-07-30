from src.data.data_pull import DataPull
import pandas as pd
import numpy as np

class DataProcess(DataPull):

    def __init__(self, saving_dir:str, agriculture:bool, debug:bool=False) -> None:
        self.saving_dir = saving_dir
        self.agriculture = agriculture
        self.debug = debug
        super().__init__(self.saving_dir, self.debug)
    
    def process_imports(self) -> pd.DataFrame:
        df = pd.read_csv("data/raw/export.csv", low_memory=False)

        df['date'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str))
        df['value'] = df['value'].astype(float)
        df.drop(['year', 'month'], axis=1, inplace=True)

        # save agriculture product
        if self.agriculture:
            agr = pd.read_json("data/external/agr_hts.json")
            agr = agr.reset_index()
            agr = agr.drop(columns=["index"])
            agr = agr.rename(columns={0:"HTS"})
            agr["HTS"] = agr["HTS"].astype(str).str.zfill(4)
            df = pd.merge(df, agr, on="HTS", how="inner")
            df = df[~df['HTS'].str.startswith(('05', '06', '14'))].reset_index()

        # remove illegal characters and remove invalid values
        df['HTS'] = df['HTS'].astype(str)
        df['HTS'] = df['HTS'].str.replace("'", '')
        df['HTS'] = df['HTS'].str.strip()
        df['HTS_dummy'] = df['HTS']
        df['unit_1'] = df['unit_1'].str.lower()
        df['HTS'] = df['HTS'].str[:4]

        # standerize all values to kg 
        df['qty'] = df['qty_1'] + df['qty_2']
        df.drop(['qty_1', 'qty_2'], axis=1, inplace=True)
        df['qty'] = df.apply(self.convertions, axis=1)
        df = df[df['qty'] > 0]

        # checkpoint
        df_checkpoint = df.copy()

        # group by date and HTS collapse
        df = df.groupby(['date', 'HTS'])[['value', 'qty']].sum().reset_index()
        df = df.sort_values(by=['date','HTS']).reset_index()
        df_labels = df_checkpoint[['HTS', 'HTS_desc']].reset_index()
        df_labels = df_labels.drop_duplicates(subset=['HTS']).reset_index()
        df = pd.merge(df, df_labels, on='HTS', how='left')

        # Get growth rate
        df['value_per_unit'] = df['value'] / df['qty']
        df['value_rolling'] = df['value_per_unit'].rolling(window=3).mean()
        df['value_growth %'] = df.groupby(['HTS'])['value_rolling'].pct_change(periods=12, fill_method=None).mul(100)
        df = df[['date', 'HTS', 'HTS_desc', 'qty', 'value',  'value_per_unit', 'value_rolling', 'value_growth %']].copy()

        return df

    def to_trimester(self, df_path, saving_path):
        df = pd.read_pickle(df_path)
        df["quarter"] = df["date"].dt.to_period("Q-JUN")
        df["Fiscal Year"] = df["quarter"].dt.qyear
        df_Qyear = df.copy()
        df_Qyear = df_Qyear.drop(['date', 'quarter'], axis=1)
        df_Qyear = df_Qyear.groupby(['Country', 'Fiscal Year']).sum().reset_index()

        # save the panel data
        df_Qyear.to_pickle(saving_path)


    def convertions(self, row) -> float:
            if row['unit_1'] == 'kg':
                return row['qty'] * 1
            elif row['unit_1'] == 'l':
                return row['qty'] * 1
            elif row['unit_1'] == 'doz':
                return row['qty'] / 0.756
            elif row['unit_1'] =='m3':
                return row['qty'] * 1560
            elif row['unit_1'] == 't':
                return row['qty'] * 907.185
            elif row['unit_1'] == 'kts':
                return row['qty'] * 1
            elif row['unit_1'] == 'pfl':
                return row['qty'] * 0.789
            elif row['unit_1'] == 'gm':
                return row['qty'] * 1000
            else:
                return np.nan
