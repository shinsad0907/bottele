import requests

def shorten_url(long_url, alias='mygame'):
    API_KEY = '7c84f034b8aca7e6023950224fa2dee5df8edfae'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://vuotlink.vip/',
    }
    
    params = {
        'api': API_KEY,
        'url': long_url,
        'alias': alias,
        # 'domain': 'oklink.cfd'
    }
    
    session = requests.Session()
    # Ghé thăm trang chủ trước để lấy cookie
    session.get('https://vuotlink.vip/', headers=headers)
    
    # Sau đó mới gọi API
    res = session.get('https://vuotlink.vip/api', params=params, headers=headers)
    
    print("Status code:", res.status_code)
    print("Response:", res.text)
    
    if res.status_code != 200:
        raise Exception(f"Bị chặn! Status: {res.status_code}")
    
    if not res.text.strip():
        raise Exception("Response rỗng!")
    
    data = res.json()
    if data['status'] == 'success':
        return data['shortenedUrl']
    else:
        raise Exception(data['message'])

link = shorten_url('https://example.com/bai-viet-rat-dai')
print('Link rút gọn:', link)