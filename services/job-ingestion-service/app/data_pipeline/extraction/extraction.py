import os

import requests

from app.data_pipeline.utils import get_token


def get_job_list(timeout_seconds: float = 20.0):
    token = get_token.get_access_token()

    url = os.getenv("FRANCE_TRAVAIL_API_SEARCH")
    if not url:
        print("FRANCE_TRAVAIL_API_SEARCH is not set")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout_seconds)
        
        # Kiểm tra lỗi HTTP (401, 403, 404, 500...)
        response.raise_for_status() 
        
        # 4. Trả về dữ liệu dạng JSON
        return response.json()
        
    except requests.exceptions.HTTPError as err:
        print(f"Lỗi HTTP: {err}")
        print(f"Chi tiết: {response.text}")  # Xem API báo lỗi gì cụ thể
        return None
    except Exception as e:
        print(f"Lỗi không xác định: {e}")
        return None


def job_search(keywords_list="", timeout_seconds: float = 20.0):
    token = get_token.get_access_token()
    
    # 2. Cấu hình URL và Headers
    url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    # keywords_list = ["python", "stage"]

    # Nối các từ khóa bằng dấu phẩy theo đúng tài liệu
    # mots_cles_param = ",".join(keywords_list)

    params = {}
    if keywords_list:
        # Nếu người dùng truyền vào list: ["python", "data"]
        if isinstance(keywords_list, list):
            # Lọc các từ khóa >= 2 ký tự và lấy tối đa 7 từ
            valid_keywords = [k for k in keywords_list if len(str(k)) >= 2][:7]
            params["motsCles"] = ",".join(valid_keywords)
        
        # Nếu người dùng chỉ truyền vào 1 string: "python"
        elif isinstance(keywords_list, str):
            if len(keywords_list) >= 2:
                params["motsCles"] = keywords_list

        params["range"] = "0-9"

    try:
        response = requests.get(
            url, headers=headers, params=params, timeout=timeout_seconds
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.JSONDecodeError:
        return {"resultats": []}
    except requests.exceptions.HTTPError as err:
        print(f"Lỗi HTTP: {err}")
        try:
            print(f"Chi tiết: {response.text}")
        except Exception:  # noqa: BLE001
            pass
        return {"resultats": []}
    except Exception as e:  # noqa: BLE001
        print(f"Lỗi không xác định: {e}")
        return {"resultats": []}