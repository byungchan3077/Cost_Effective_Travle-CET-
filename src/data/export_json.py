import pandas as pd
import json
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

# 1. 국가명 통일 맵
name_standardize_map = {
    "Britain": "UK",
    "United Kingdom": "UK",
    "United States": "USA",
    "Hongkong": "Hong Kong", 
    "Hong Kong": "Hong Kong",
    "United Arab Emirates": "UAE"
}

# 2. 통화 매핑
currency_map = {
    "Japan": "JPY(100)",
    "USA": "USD",
    "Italy": "EUR",
    "Spain": "EUR",
    "France": "EUR",
    "Austria": "EUR",
    "Indonesia": "IDR(100)",
    "UK": "GBP",
    "Singapore": "SGD",
    "Thailand": "THB",
    "Hong Kong": "HKD",
    "UAE": "AED",
    "Vietnam": "VND(100)",
    "Taiwan": "TWD",
}

# 3. 유로존 국가 목록
euro_zone_countries = ["France", "Italy", "Spain", "Austria"]

def load_and_process_data():
    hotel_path = os.path.join(script_dir, "hotel_price_index.csv")
    starbucks_path = os.path.join(script_dir, "starbucks_drink_index.csv")
    bigmac_path = os.path.join(script_dir, "big_mac_index.csv")
    
    try:
        hotel = pd.read_csv(hotel_path)
        starbucks = pd.read_csv(starbucks_path)
        bigmac = pd.read_csv(bigmac_path) 
    except FileNotFoundError as e:
        print(f"❌ 파일을 찾을 수 없습니다: {e}")
        return None

    # --- 1단계: 공백 제거 및 컬럼 정리 ---
    hotel = hotel.rename(columns={"Avg_price": "avg_hotel_krw"})
    starbucks = starbucks.rename(columns={"Avg_price": "starbucks_price"})
    bigmac = bigmac.rename(columns={"local_price": "bigmac_price"})

    # [수정됨] 가격 데이터 강제 숫자 변환 (에러 방지 핵심!)
    # errors='coerce'는 숫자로 바꿀 수 없는 데이터가 있으면 NaN(빈값)으로 처리하라는 뜻
    hotel["avg_hotel_krw"] = pd.to_numeric(hotel["avg_hotel_krw"], errors='coerce')
    starbucks["starbucks_price"] = pd.to_numeric(starbucks["starbucks_price"], errors='coerce')
    bigmac["bigmac_price"] = pd.to_numeric(bigmac["bigmac_price"], errors='coerce')

    # 국가명 공백 제거
    for df in [hotel, starbucks, bigmac]:
        if "Country" in df.columns:
            df["Country"] = df["Country"].astype(str).str.strip()

    # --- 2단계: 국가별 평균 계산 ---
    # 이제 가격이 확실히 숫자이므로 mean()에서 오류가 나지 않습니다.
    hotel = hotel.groupby("Country")[["avg_hotel_krw"]].mean().reset_index()
    starbucks = starbucks.groupby("Country")[["starbucks_price"]].mean().reset_index()

    # --- 3단계: 유로존 데이터 증식 ---
    euro_row = bigmac[bigmac["Country"] == "Euro area"]
    if not euro_row.empty:
        euro_price = euro_row.iloc[0]["bigmac_price"]
        new_rows = []
        for country in euro_zone_countries:
            new_rows.append({"Country": country, "bigmac_price": euro_price})
        
        euro_df = pd.DataFrame(new_rows)
        bigmac = pd.concat([bigmac, euro_df], ignore_index=True)

    # --- 4단계: 국가명 표준화 ---
    hotel["Country"] = hotel["Country"].replace(name_standardize_map)
    starbucks["Country"] = starbucks["Country"].replace(name_standardize_map)
    bigmac["Country"] = bigmac["Country"].replace(name_standardize_map)

    # --- 5단계: 데이터 병합 ---
    merged = bigmac.merge(starbucks, on="Country", how="inner")
    merged = merged.merge(hotel, on="Country", how="inner")
    
    # 혹시 모를 결측치(NaN)는 0으로 채움
    merged = merged.fillna(0)

    # --- 6단계: 통화 코드 및 최종 데이터 정리 ---
    merged["currency_code"] = merged["Country"].map(currency_map)
    
    result = {}
    for _, row in merged.iterrows():
        country_name = row["Country"]
        result[country_name] = {
            "currency": row["currency_code"] if row["currency_code"] != 0 else "Unknown",
            "big_mac": round(row["bigmac_price"], 2),
            "starbucks": round(row["starbucks_price"], 2),
            "avg_hotel_krw": round(row["avg_hotel_krw"], 0),
        }
    
    return result

if __name__ == "__main__":
    data = load_and_process_data()
    
    if data:
        print("\n" + "="*50)
        print(f"📊 처리 완료! 총 {len(data)}개 국가 데이터 생성됨")
        print("="*50)
        print(json.dumps(data, indent=4, ensure_ascii=False))
        
        output_path = os.path.join(script_dir, "result.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print("="*50 + "\n")