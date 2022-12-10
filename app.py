# -*- coding: utf-8 -*-
# 时间: 2022/12/9 12:31
# 作者: 陈子含
# 功能: 识别发票并保存到excel
import io
import time
import streamlit as st
import os

import pandas as pd
import requests
import base64
from glob import glob

import base64
import requests


def get_file_content_as_base64(path):
    """
    获取文件base64编码
    :param path: 文件路径
    :return: base64编码信息
    """
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf8")


def get_access_token(API_KEY, SECRET_KEY):
    """
    使用 AK，SK 生成鉴权签名（Access Token）
    :return: access_token，或是None(如果错误)
    """
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {"grant_type": "client_credentials", "client_id": API_KEY, "client_secret": SECRET_KEY}
    return str(requests.post(url, params=params).json().get("access_token"))


def ocr_response(file, access_token):
    '''
    增值税发票识别
    '''
    # request_url指定了选用的功能
    request_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/vat_invoice"
    if isinstance(file, str):
        # file是路径名
        with open(file, 'rb') as f:
            img = base64.b64encode(f.read())
    else:
        # file是文件流
        img = base64.b64encode(file)
    params = {"image": img}
    request_url = request_url + "?access_token=" + access_token
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    response = requests.post(request_url, data=params, headers=headers)
    if response:
        return response.json()['words_result']


def dict_process(d):
    """
    对发票识别得到的字典进行解析，得到新的字典
    """
    c_num = len(d['CommodityName'])
    commodity = [(d['CommodityName'][i]['word'], d['CommodityAmount'][i]['word'], d['CommodityTaxRate'][i]['word'],
                  d['CommodityTax'][i]['word']) for i in range(c_num)]
    name, amount, tr, tax = zip(*commodity)
    out = {
        '发票代码': d['InvoiceCodeConfirm'],
        '发票编号': d['InvoiceNumConfirm'],
        '机器编号': d['MachineCode'],
        '开票日期': d['InvoiceDate'],
        '购买方 名称': d['PurchaserName'],
        '购买方 纳税人识别号': d['PurchaserRegisterNum'],
        '购买方 地址、电话': d['PurchaserAddress'],
        '购买方 开户行及账号': d['PurchaserBank'],
        '货物或应税劳务、服务名称': '\n'.join(name),
        '金额': '\n'.join(amount),
        '税率': '\n'.join(tr),
        '税额': '\n'.join(tax),
        '合计金额': d['TotalAmount'],
        '合计税额': d['TotalTax'],
        '价税合计': d['AmountInFiguers'],
        '销售方 名称': d['SellerName'],
        '销售方 纳税人识别号': d['SellerRegisterNum'],
        '销售方 地址、电话': d['SellerAddress'],
        '销售方 开户行及账号': d['SellerBank'],
        '备注': d['Remarks'],
    }
    return out


@st.cache
def main(files, out_path=None):
    ak = '0iZ12lvhS6ZpWiPiwSCMAGCH'
    sk = '9fFD0Co9TG3KVo7Nm3YVh9sBw6FPlALq'
    access_token = get_access_token(ak, sk)
    df = pd.DataFrame(columns=['文件名', '发票代码', '发票编号', '机器编号', '开票日期', '购买方 名称', '购买方 纳税人识别号',
                               '购买方 地址、电话', '购买方 开户行及账号', '货物或应税劳务、服务名称', '金额', '税率', '税额',
                               '合计金额', '合计税额', '价税合计', '销售方 名称', '销售方 纳税人识别号', '销售方 地址、电话',
                               '销售方 开户行及账号', '备注'], dtype=str)
    df = df.astype({i: 'float64' for i in ['金额', '税额', '合计金额', '合计税额', '价税合计']})
    InvoiceNumConfirm = []
    for i, (file, name) in enumerate(files):
        try:
            out_i = dict_process(ocr_response(file, access_token))
            if out_i['发票编号'] not in InvoiceNumConfirm:
                InvoiceNumConfirm.append(out_i['发票编号'])
                df.loc[i] = out_i
                df.loc[i, '文件名'] = name
        except:
            df.loc[i, '文件名'] = name
            continue
    return df


def download_df(df):
    buf = io.BytesIO()
    df.to_excel(buf, index=False, encoding='gbk')
    return buf


def post_process(df: pd.DataFrame):
    or_cols = ['发票代码', '发票编号', '货物或应税劳务、服务名称', '开票类型', '价税合计', '税率', '合计税额', '合计金额']
    cols = ['发票代码', '发票编号', '发票名称', '开票类型', '发票金额（含税）', '税率%', '税额', '发票金额（不含税）']
    df.loc[:, '开票类型'] = '增值税专用发票'
    do = df.reindex(columns=['发票代码', '发票编号', '货物或应税劳务、服务名称', '开票类型', '价税合计', '税率', '合计税额', '合计金额'])
    c = {or_cols[i]: col for i, col in enumerate(cols)}
    dfp = do.rename(columns=c)
    return dfp


if __name__ == '__main__':
    st.set_page_config(page_title='发票识别',
                       page_icon="wind.ico",
                       layout="wide",
                       initial_sidebar_state="auto")
    st.title('增值税发票识别与导出')
    st.subheader('选择增值税发票文件')
    files_load = st.file_uploader("发票上传", accept_multiple_files=True, label_visibility="collapsed")
    file_names = []
    files = []
    if files_load:
        for file in files_load:
            file_names.append(file.name)
            files.append((file.getvalue(), file.name))
        st.table(file_names)
        st.subheader("分析与导出")
        if st.button('开始分析') and files:
            df = main(files)
            st.dataframe(df)
            st.download_button('导出', data=download_df(df), file_name=f'发票识别_{time.strftime("%Y%m%d_%H%M%S")}.xlsx')



