import json
import requests
import base64
import csv
import random

def make_dict(total_numbers, city, isp):
    # 解码URL和Headers
    url = base64.b64decode("aHR0cDovL2FwcC53ZXdlNzc4OC5jbjo4MC9hcHAvUXVlcnlTaHVmZmxlQ29kZT90b2tlbj0=").decode('utf-8')
    headers = json.loads(base64.b64decode(
        "eyJBY2NlcHQtRW5jb2RpbmciOiAiZGVmbGF0ZSwgZ3ppcCIsICJPcmlnaW4iOiAiaHR0cDovL2FwcC53ZXdlNzc4OC5jbiIsICJYLVJlcXVlc3RlZC1XaXRoIjogIlhNTEh0dHBSZXF1ZXN0IiwgIlVzZXItQWdlbnQiOiAiTW96aWxsYS81LjAgKFdpbmRvd3M7IFU7IFdpbmRvd3MgTlQgNi4yOyB6aC1DTikgQXBwbGVXZWJLaXQvNTMzKyAoS0hUTUwsIGxpa2UgR2Vja28pIiwgIkNvbnRlbnQtVHlwZSI6ICJhcHBsaWNhdGlvbi94LXd3dy1mb3JtLXVybGVuY29kZWQ7IGNoYXJzZXQ9VVRGLTgiLCAiQWNjZXB0IjogImFwcGxpY2F0aW9uL2pzb24sIHRleHQvamF2YXNjcmlwdCwgKi8qOyBxPTAuMDEiLCAiUmVmZXJlciI6ICJodHRwOi8vYXBwLndld2U3Nzg4LmNuL2FwcC9mbGFzaCJ9").decode('utf-8'))
    # 请求数据
    data = {"total": total_numbers, "city": city, "isp": isp}
    response = requests.post(url, headers=headers, data=data)
    data = response.json()
    prefix = data['prefix']
    suffix = data['suffix']
    prefixInfo = data['prefixInfo']
    no = 0

    # 创建用于跟踪已使用前缀和手机号的集合
    used_prefixes = set()
    used_phone_numbers = set()

    # 将前缀和前缀信息组合并打乱顺序
    prefix_info_list = list(zip(prefix, prefixInfo))
    random.shuffle(prefix_info_list)
    random.shuffle(suffix)

    with open("telephone_number_dict.csv", "w", encoding="UTF-8", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["手机号", "手机号归属地"])
        for pref, pref_info in prefix_info_list:
            if pref in used_prefixes:
                continue
            for suff in suffix:
                phoneNum = pref + suff
                if phoneNum in used_phone_numbers:
                    continue
                phoneInfo = pref_info['province'] + pref_info['city'] + pref_info['isp']
                print(phoneNum, phoneInfo)
                writer.writerow([phoneNum, phoneInfo])
                used_prefixes.add(pref)
                used_phone_numbers.add(phoneNum)
                no += 1
                if no >= total_numbers:
                    break
            if no >= total_numbers:
                break
    print("[*]手机号字典（telephone_number_dict.csv）生成成功，共计生成：{}条，请打开字典查看详细内容！".format(no))

if __name__ == '__main__':
    try:
        print(""" __  __       _        ____  _                      ____  _      _   
|  \/  | __ _| | _____|  _ \| |__   ___  _ __   ___|  _ \(_) ___| |_ 
| |\/| |/ _` | |/ / _ \ |_) | '_ \ / _ \| '_ \ / _ \ | | | |/ __| __|
| |  | | (_| |   <  __/  __/| | | | (_) | | | |  __/ |_| | | (__| |_ 
|_|  |_|\__,_|_|\_\___|_|   |_| |_|\___/|_| |_|\___|____/|_|\___|\__|
Hx0战队-手机号字典生成器V1.1               Update:2023.11.07                                        
        """)
        total_numbers = 20  # 生成20个号码
        city = "1201"  # 天津的城市区域代码
        isp = "4001,4006,4008"  # 三个运营商
        make_dict(total_numbers, city, isp)
    except Exception as e:
        print(e)
