import pandas as pd
import ast
from typing import Union, Dict, Any

ValType = Union[str, Dict[str, Any], None]

import json

def extract_lieu_travail_detailed(val: ValType) -> pd.Series:
    # Trả về các giá trị mặc định nếu dữ liệu rỗng
    default_values = {
        'lieu_libelle': '', 
        'latitude': None, 
        'longitude': None, 
        'codePostal': '', 
        'commune': ''
    }
    
    if pd.isna(val) or val == "" or val == "{}":
        
        return pd.Series(default_values)
    
    try:
        # Chuyển chuỗi thành dict
        
        lieu = json.loads(val.replace("'", '"')) if isinstance(val, str) else val
        
        
        return pd.Series({
            'libelle': lieu.get('libelle', ''),
            'latitude': lieu.get('latitude', None),
            'longitude': lieu.get('longitude', None),
            'codePostal': lieu.get('codePostal', ''),
            'commune': lieu.get('commune', '')
        })
    except:
        return pd.Series(default_values)
    
def extract_entreprise_info(val: ValType) -> pd.Series:
    default = {'entreprise_nom': '', 'description_entreprise': '', 'entrepriseAdaptee': ''}
    if pd.isna(val) or val == "" or val == "{}":
        return pd.Series(default)
    
    try:
        # Nếu val là string và có chứa dấu escape \', chúng ta cần xử lý
        if isinstance(val, str):
            societe = ast.literal_eval(val)
            
        else:
            societe = val
        return pd.Series({
            'entreprise_nom': societe.get('nom', ''),
            'description_entreprise': societe.get('description', ''),
            'entrepriseAdaptee': str(societe.get('entrepriseAdaptee', ''))
        })
    except Exception:
        return pd.Series(default)
