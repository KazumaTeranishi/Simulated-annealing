# -*- coding: utf-8 -*-

from simanneal import Annealer#pip install simannealを実行すること

import numpy as np
import random
import os.path
import pandas as pd#pip install pandasを実行すること
import io
import heapq
from os import path
import time
import math
import copy

print(path.splitext(path.basename(__file__))[0])

#条件ファイルの読み込み
cycletime = pd.read_csv(path.join(path.dirname(__file__), 'cycletime_by_specification.csv'))
ms = pd.read_csv(path.join(path.dirname(__file__), 'manufacturing_sequence.csv'))
id_flame = pd.read_csv(path.join(path.dirname(__file__), 'Relationship_bw_ID_FlameSpec.csv'))
id_maru_a = pd.read_csv(path.join(path.dirname(__file__), 'Relationship_bw_ID_SheetSpec.csv'))

#計算条件
#ロット数の定義
Lot_num = 5#len(ms)
Lot_set = np.zeros(1,np.int32)
num_step = 300000#総計算回数(300台の時に10万回計算に相当する）
num_rotation = 10 #初期ロットから再計算する回数
num_repeat = 10#繰り返し実行数
_4way_replace_flag = False#True#False#True#False#4wayの並び替え制限:Trueで制限あり、Falseで制限なし
_maru_A_replace_flag =True#False#True#False#〇A仕様の並び替え制限:Trueで制限あり、Falseで制限なし
_maru_A_replace_renzoku_flag =True#True#False#True#False#〇A仕様の並び替えを同一仕様が連続している回数で制限する:Trueで制限あり、Falseで制限なし
_maru_A_replace_SA_flag =False#True#False#True#False#〇A仕様の並び替えを同一仕様が連続している回数で制限する.SAで最小化する:Trueで制限あり、Falseで制限なし

##pwr_replace_flag = True#False#〇Aの並び替え制限:Trueで制限あり、Falseで制限なし
##heater_replace_flag = True#False#〇Aの並び替え制限:Trueで制限あり、Falseで制限なし
##leather_replace_flag = True#False#〇Aの並び替え制限:Trueで制限あり、Falseで制限なし
##tr_replace_flag = True#False#〇Aの並び替え制限:Trueで制限あり、Falseで制限なし
##cartype_replace_flag = True#False#〇Aの並び替え制限:Trueで制限あり、Falseで制限なし

maru_a_replace = np.array([1,1,1,1,1,1])
    
num_step = int(num_step * len(ms)/300)

#エクセルのVlookUpの機能を再現する箇所
ms_n = np.arange(0,len(ms)*2).reshape((len(ms)*2,1))#データを入れる箱の準備
ms_df= pd.DataFrame(ms_n, columns=["manufacturing_sequence"])#データベース型に変換（VlookUp機能を使えるようにするため）
ms_df['manufacturing_sequence_s'] = ms_df['manufacturing_sequence'].astype(str)#データを文字型に変換（VlookUp機能を使えるようにするため）

ms2 = copy.deepcopy(ms)

#シートをRHとLHに分離
for i in range(len(ms)):
    ms_df.iat[i*2,1] = ms.iat[i,0] + "RH"
    ms_df.iat[i*2+1,1] = ms.iat[i,0]+ "LH"

#VlookUpでデータを結合 
df1_1 = pd.merge(ms_df, id_flame , how="left", left_on="manufacturing_sequence_s", right_on="ID+Hand")
df1_2 = pd.merge(df1_1 , cycletime , how="left", left_on="ID_RH", right_on="ID")
df1_3 = pd.merge(ms , id_maru_a , how="left", left_on="manufacturing_sequence", right_on="ID")
df2 = df1_2.iloc[:, 15:22]
df3 = df1_2.iloc[:, 8]
df4 = df1_3.iloc[:, 2:8] * maru_a_replace

#計算を高速化するためにDataframeからNumpy配列に変換
n_df2 = df2.values
n_df3 = df3.values
n_df4 = df2.values
n_df5 = df4.values
n_df6 = df4.values
n_df7 = df4.values

for m in range(0,len(n_df5)):
 n_df5[m,5] = (n_df5[m,0] * 10000 +
             n_df5[m,1] * 1000 +
             n_df5[m,2] * 100 +
             n_df5[m,3] * 10 +
             n_df5[m,4] * 1)

n_df6 = copy.deepcopy(n_df5)
n_df7 = copy.deepcopy(n_df5)

#計算を高速化するために整数化
#n_df2  = n_df2 *100
#n_df4  = n_df4 *100
n_df2.astype(np.float64)
n_df4.astype(np.float64)

ID = list(range(len(ms)*2))

ID_maru_a = list(range(len(ms)))

#データを入れる箱準備(0が工程時間開始(act),1が工程時間終了(ideal),脚番号,工程順 0:溶接～5:チルト)
Time_df = np.zeros((2,len(ms)*2,6),np.float64)
Time_df_previous = np.zeros((2,len(ms)*2,6),np.float64)
Time_df_previous_intermidiate = np.zeros((2,len(ms)*2,6),np.float64)
Time_df_best_process = np.zeros((2,len(ms)*2,6),np.float64)
Time_df_best = np.zeros((2,len(ms)*2,6),np.float64)#np.zeros((2,len(ms)*2,6))

Time_df_temp1 = np.zeros(6,np.float64)
Time_df_temp2 = np.zeros(6,np.float64)
Time_df_temp1_m1 = np.zeros(6,np.float64)
Time_df_temp2_m1 = np.zeros(6,np.float64)

Time_df_Lot = np.zeros((2,Lot_num*2 + 8,6),np.float64)

n_df2_temp = np.zeros(6,np.float64)

n_df5_temp1 = np.zeros(len(n_df5[0,:]),np.float64)
n_df5_temp2 = np.zeros(len(n_df5[0,:]),np.float64)
n_df5_temp3 = np.zeros(len(n_df5[0,:]),np.float64)
n_df5_temp4 = np.zeros(len(n_df5[0,:]),np.float64)
           
#チルト工程終了時間の遅い順から2つ取り出すための箱を準備
Top1_2 = np.zeros(2,np.float64)#,np.int32)

#入れ替え番号をどこでも使えるようにグローバルで定義
a_g = np.zeros(1,np.int32)
b_g = np.zeros(1,np.int32)

#コスト関数のアップデートの判定を記録するためのフラグ
cost_update = np.zeros(1,np.int32)
cost_update_4way = np.zeros(1,np.int32)
cost_update_4way_ab = np.zeros(1,np.int32)

#ステップ数を定義
step_n = np.zeros(1,np.int32)

#総工程時間の格納場所を定義
Total_estimated_time = np.zeros(2,np.float64)
Total_estimated_time_previous  = np.zeros(2,np.float64)
Total_estimated_time_previous_intermidiate = np.zeros(2,np.float64)

#評価関数のみの値を取り出す際の変数
energy_n = np.zeros(1,np.int32)
counter_u = 0

#SAの本体
class GroupingProblem(Annealer):

    def __init__(self, init_state):
        super(GroupingProblem, self).__init__(init_state)

    # 探索点の移動ルール
    def move(self):
        global n_df2
        global n_df3
        global n_df4
        global cost_update
        global Time_df
        global Time_df_best
        global Time_df_best_process
        global Time_df_previous
        global Time_df_previous_intermidiate

        cost_update[0] = 0

        #データベースdf_2の0列目以降に工程時間が格納
        j_num1 = 0

        #コスト関数が小さくならかった場合、ライブラリ内でself.stateを前回のself.stateに置換している。
        #self.stateが前回の順番に戻ったことを判断して、各条件を前回の値に戻す
        if self.state[a_g[0]] != ms_list_t[a_g[0]] or self.state[b_g[0]] != ms_list_t[b_g[0]] :

            #フラグを立てる（コスト関数計算用)
            cost_update[0] = 1

            #並び替えた方法次第で戻し方が異なる
            if cost_update_4way[0] != 0:


               if b_g[0] == cost_update_4way_ab[0]:

                  a = a_g[0]
                  b = b_g[0]
                  m = a

                  for i in range(0,600):
                        if a > b:

                           #工程時間の入れ替え
                           ID[m*2] , ID[(m-1)*2] = ID[(m-1)*2], ID[m*2]
                           ID[m*2+1] , ID[(m-1)*2+1] = ID[(m-1)*2+1], ID[m*2+1]

                           #組み立て仕様の入れ替え
                           n_df3[m*2] , n_df3[(m-1)*2] = n_df3[(m-1)*2], n_df3[m*2]
                           n_df3[m*2+1] , n_df3[(m-1)*2+1] = n_df3[(m-1)*2+1], n_df3[m*2+1]

                           ms_list_t[m], ms_list_t[(m-1)] =ms_list_t[(m-1)] ,ms_list_t[m]

                           m = m - 1

                        else:

                           #工程時間の入れ替え
                           ID[m*2] , ID[(m+1)*2] = ID[(m+1)*2], ID[m*2]
                           ID[m*2+1] , ID[(m+1)*2+1] = ID[(m+1)*2+1], ID[m*2+1]

                           #組み立て仕様の入れ替え
                           n_df3[m*2] , n_df3[(m+1)*2] = n_df3[(m+1)*2], n_df3[m*2]
                           n_df3[m*2+1] , n_df3[(m+1)*2+1] = n_df3[(m+1)*2+1], n_df3[m*2+1]

                           ms_list_t[m], ms_list_t[(m+1)] =ms_list_t[(m+1)] ,ms_list_t[m]

                           m = m + 1

                        if b == m:
                            break

               elif a_g[0] == cost_update_4way_ab[0]:

                  a = a_g[0]
                  b = b_g[0]
                  m = b

                  for i in range(0,600):
                        if a > b:

                          #工程時間の入れ替え
                           ID[m*2] , ID[(m+1)*2] = ID[(m+1)*2], ID[m*2]
                           ID[m*2+1] , ID[(m+1)*2+1] = ID[(m+1)*2+1], ID[m*2+1]

                           #組み立て仕様の入れ替え
                           n_df3[m*2] , n_df3[(m+1)*2] = n_df3[(m+1)*2], n_df3[m*2]
                           n_df3[m*2+1] , n_df3[(m+1)*2+1] = n_df3[(m+1)*2+1], n_df3[m*2+1]

                           ms_list_t[m], ms_list_t[(m+1)] =ms_list_t[(m+1)] ,ms_list_t[m]

                           m = m + 1

                        else:

                           #工程時間の入れ替え
                           ID[m*2] , ID[(m-1)*2] = ID[(m-1)*2], ID[m*2]
                           ID[m*2+1] , ID[(m-1)*2+1] = ID[(m-1)*2+1], ID[m*2+1]

                           #組み立て仕様の入れ替え
                           n_df3[m*2] , n_df3[(m-1)*2] = n_df3[(m-1)*2], n_df3[m*2]
                           n_df3[m*2+1] , n_df3[(m-1)*2+1] = n_df3[(m-1)*2+1], n_df3[m*2+1]

                           ms_list_t[m], ms_list_t[(m-1)] =ms_list_t[(m-1)] ,ms_list_t[m]

                           m = m - 1

                        if a == m:
                            break

            else:

               #並び替え
               ms_list_t[a_g[0]], ms_list_t[b_g[0]] = ms_list_t[b_g[0]] ,ms_list_t[a_g[0]]

               #工程時間の入れ替え
               ID[a_g[0]*2] , ID[b_g[0]*2] = ID[b_g[0]*2], ID[a_g[0]*2]
               ID[a_g[0]*2+1] , ID[b_g[0]*2+1] = ID[b_g[0]*2+1], ID[a_g[0]*2+1]

               #組み立て仕様の入れ替え
               n_df3[a_g[0]*2] , n_df3[b_g[0]*2] = n_df3[b_g[0]*2], n_df3[a_g[0]*2]
               n_df3[a_g[0]*2+1] , n_df3[b_g[0]*2+1] = n_df3[b_g[0]*2+1], n_df3[a_g[0]*2+1]

               #組み立て仕様の入れ替え2
               ID_maru_a[a_g[0]] , ID_maru_a[b_g[0]] = ID_maru_a[b_g[0]], ID_maru_a[a_g[0]]
               n_df5[:,:] = n_df6[ID_maru_a,:]

            n_df2 = n_df4[ID,:]
##            print("AAA")

        cost_update_4way[0] = 0

        if _4way_replace_flag:
            c = 0
            d = 0
        else:
            c = 1
            d = 1
            if _maru_A_replace_flag:

                if _maru_A_replace_renzoku_flag:

                   #現在の並び順での使用連続数をカウントする
                    n_df5_temp1 = np.zeros(len(n_df6[0,:]),np.float64)
                    n_df5_temp2 = np.zeros(len(n_df6[0,:]),np.float64)
                    Tfactor2 = -math.log(self.Tmax / self.Tmin)
                    T = self.Tmax * math.exp(Tfactor2 * step_n[0] / self.steps)                   
                    if _maru_A_replace_SA_flag:
                       T_n = - int(2/(1+math.exp(-(math.log(T)-2.5))))
                    else:
                       T_n = 0
                    #print(n_df5_temp)
                       
                    if Lot_set[0] * Lot_num == 0:
                       Start_k = 0
                    else:
                       Start_k = Lot_set[0] * Lot_num -1

                    if (Lot_set[0] + 1) * Lot_num > len(ms)-1:
                       
                       End_k = len(ms)-1
                       
                    else:
                       
                       End_k = (Lot_set[0] + 1) * Lot_num#len(ms)-1
                       
                    #for k in range(Lot_set[0] * Lot_num,min(((Lot_set[0] + 1) * Lot_num),len(ms)-1)):
##                    for k in range(0,len(ms)-1):
                    for k in range(Start_k,End_k):
                       for l in range(len(n_df7[0,:])):
                           if n_df5[k,l] == n_df5[k+1,l] and n_df5[k,l] == 1:
                              n_df5_temp1[l] =  n_df5_temp1[l] + 1
##                    print(n_df5_temp1) 
                    a = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
                    b = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
                    for j in range(0,50):
                             if j > 48:
                               a = b
                               break
                             if n_df3[a*2] == n_df3[b*2] and n_df3[a*2+1] == n_df3[b*2+1]:
                                b = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
                                continue
                                
                             ID_maru_a[a] , ID_maru_a[b] = ID_maru_a[b], ID_maru_a[a]
                             n_df5[:,:] = n_df6[ID_maru_a,:]
                             
                             n_df5_temp2 = np.zeros(len(n_df6[0,:]),np.float64)
                             for k in range(Start_k,End_k):
                                for l in range(len(n_df5[0,:])):
                                    if n_df5[k,l] == n_df5[k+1,l] and n_df5[k,l] == 1:
                                       n_df5_temp2[l] =  n_df5_temp2[l] + 1
                             n_df5_temp3 = (n_df5_temp1-n_df5_temp2) * maru_a_replace
                             if np.min(n_df5_temp3) < T_n:
                               ID_maru_a[a] , ID_maru_a[b] = ID_maru_a[b], ID_maru_a[a]
                               a = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
                               continue
                             else:
##                               print("--",j,n_df5_temp2,T_n)
                               break
                    
##                    if np.min(n_df5_temp3) < T_n:
##                      print("--",j,n_df5_temp3,T_n)

                else:   
                    a = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
                    b = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
                    if n_df3[a*2] == n_df3[b*2] and n_df3[a*2+1] == n_df3[b*2+1] or n_df5[a,5] != n_df5[b,5]:
                       for j in range(0,600):
                         b = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
                         if n_df5[a,5] == n_df5[b,5]:#同じ〇A仕様しか並び替えを認めない
                            if n_df3[a*2] != n_df3[b*2] or n_df3[a*2+1] != n_df3[b*2+1]:
                               ID_maru_a[a] , ID_maru_a[b] = ID_maru_a[b], ID_maru_a[a]
                               n_df5[:,:] = n_df6[ID_maru_a,:]
                               break
                         if j > 598:
                            a = b
                            
                

            else:
                a = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
                b = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
                if n_df3[a*2] == n_df3[b*2] and n_df3[a*2+1] == n_df3[b*2+1]:
                   for j in range(0,600):
                     b = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
                     if n_df3[a*2] != n_df3[b*2] or n_df3[a*2+1] != n_df3[b*2+1]:
                        break       
        e = 0
        count_repeat =0

        #4wayの制約
        if _4way_replace_flag:
             for i in range(0,500):#while c == 0 and d == 0:# or a == b
      
               a = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
               b = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
               if n_df3[a*2] == n_df3[b*2] and n_df3[a*2+1] == n_df3[b*2+1]:
                    for j in range(0,600):
                      b = random.randint(0 + Lot_set[0] * Lot_num , (Lot_set[0] + 1) * Lot_num-1)
                      if n_df3[a*2] != n_df3[b*2] or n_df3[a*2+1] != n_df3[b*2+1]:
                         break

               c = n_df2[a*2,j_num1+5] * n_df2[a*2+1,j_num1+5]
               d = n_df2[b*2,j_num1+5] * n_df2[b*2+1,j_num1+5]

               count_repeat = count_repeat + 1

               if  count_repeat > Lot_num:
                   a = b
     ##              print("Retry")
                   c = 1
                   d = 1
                   break
               #仕様が同じであれば入れ替え可能
               if n_df3[a*2] == n_df3[b*2] and n_df3[a*2+1] == n_df3[b*2+1]:
     ##              print(n_df3[a*2],n_df3[b*2],n_df3[a*2+1],n_df3[b*2+1])
                   c = 1
                   d = 1
                   break

               if(n_df3[a*2] == "72010X7V10" and n_df3[a*2+1] == "74020X7V25" or
                  n_df3[a*2] == "72010X7V10" and n_df3[a*2+1] == "72020X7V71"):

                  if(n_df3[b*2] == "72010X7V10" and n_df3[b*2+1] == "74020X7V25" or
                     n_df3[b*2] == "72010X7V10" and n_df3[b*2+1] == "72020X7V71"):
                         #print(n_df3[a*2],n_df3[b*2],n_df3[a*2+1],n_df3[b*2+1])
                         #print("AAA")
                         c = 1
                         d = 1
                         break

               if(n_df3[a*2] == "72010X7V31" and n_df3[a*2+1] == "72020X7V07" or
                  n_df3[a*2] == "72010X7V75" and n_df3[a*2+1] == "72020X7V07"):

                  if(n_df3[b*2] == "72010X7V31" and n_df3[b*2+1] == "72020X7V07" or
                     n_df3[b*2] == "72010X7V75" and n_df3[b*2+1] == "72020X7V07"):
                         #print(n_df3[a*2],n_df3[b*2],n_df3[a*2+1],n_df3[b*2+1])
                         #print("BBB")
                         c = 1
                         d = 1
                         break

               if(n_df3[a*2] == "72010X7V73" and n_df3[a*2+1] == "72020X7V47" or
                  n_df3[a*2] == "72010X7V73" and n_df3[a*2+1] == "74020X7V26"):

                  if(n_df3[b*2] == "72010X7V73" and n_df3[b*2+1] == "72020X7V47" or
                     n_df3[b*2] == "72010X7V73" and n_df3[b*2+1] == "74020X7V26"):
                         #print(n_df3[a*2],n_df3[b*2],n_df3[a*2+1],n_df3[b*2+1])
                         #print("CCC")
                         c = 1
                         d = 1
                         break
              
               if c != 0 or d != 0:
                  break
                 
        a_g[0] = a
        b_g[0] = b

             #print("A",int((time.time()-Time_A)*1000000))
             #Time_A =time.time()
             
        if c == 0 and d != 0:
##           print("C")

           cost_update_4way[0] = 1
           cost_update_4way_ab[0] = b
##           print("b",cost_update_4way_ab[0],ms_list_t[b_g[0]],self.state[b_g[0]],a)
           m = b
           
           for i in range(0,600):

                 if a > b:
                    self.state[m], self.state[m + 1] = self.state[m + 1], self.state[m]

                    #工程時間の入れ替え
                    ID[m*2] , ID[(m+1)*2] = ID[(m+1)*2], ID[m*2]
                    ID[m*2+1] , ID[(m+1)*2+1] = ID[(m+1)*2+1], ID[m*2+1]

                    #組み立て仕様の入れ替え
                    n_df3[m*2] , n_df3[(m+1)*2] = n_df3[(m+1)*2], n_df3[m*2]
                    n_df3[m*2+1] , n_df3[(m+1)*2+1] = n_df3[(m+1)*2+1], n_df3[m*2+1]

                    ms_list_t[m], ms_list_t[(m+1)] =ms_list_t[(m+1)] ,ms_list_t[m]

                    m = m + 1

                 else:
                    self.state[m], self.state[m - 1] = self.state[m - 1], self.state[m]

                    #工程時間の入れ替え
                    ID[m*2] , ID[(m-1)*2] = ID[(m-1)*2], ID[m*2]
                    ID[m*2+1] , ID[(m-1)*2+1] = ID[(m-1)*2+1], ID[m*2+1]

                    #組み立て仕様の入れ替え
                    n_df3[m*2] , n_df3[(m-1)*2] = n_df3[(m-1)*2], n_df3[m*2]
                    n_df3[m*2+1] , n_df3[(m-1)*2+1] = n_df3[(m-1)*2+1], n_df3[m*2+1]

                    ms_list_t[m], ms_list_t[(m-1)] =ms_list_t[(m-1)] ,ms_list_t[m]

                    m = m - 1

                 if a == m:
                    break
           

        elif c !=0 and d == 0:
           
           cost_update_4way[0] = 1
           cost_update_4way_ab[0] = a
           
           m = a

           for i in range(0,600):#while b != m:

                 if a > b:
                    self.state[m], self.state[m - 1] = self.state[m - 1], self.state[m]

                    #工程時間の入れ替え
                    ID[m*2] , ID[(m-1)*2] = ID[(m-1)*2], ID[m*2]
                    ID[m*2+1] , ID[(m-1)*2+1] = ID[(m-1)*2+1], ID[m*2+1]

                    #組み立て仕様の入れ替え
                    n_df3[m*2] , n_df3[(m-1)*2] = n_df3[(m-1)*2], n_df3[m*2]
                    n_df3[m*2+1] , n_df3[(m-1)*2+1] = n_df3[(m-1)*2+1], n_df3[m*2+1]

                    ms_list_t[m], ms_list_t[(m-1)] =ms_list_t[(m-1)] ,ms_list_t[m]

                    m = m - 1

                 else:
                    self.state[m], self.state[m + 1] = self.state[m + 1], self.state[m]

                    #工程時間の入れ替え
                    ID[m*2] , ID[(m+1)*2] = ID[(m+1)*2], ID[m*2]
                    ID[m*2+1] , ID[(m+1)*2+1] = ID[(m+1)*2+1], ID[m*2+1]

                    #組み立て仕様の入れ替え
                    n_df3[m*2] , n_df3[(m+1)*2] = n_df3[(m+1)*2], n_df3[m*2]
                    n_df3[m*2+1] , n_df3[(m+1)*2+1] = n_df3[(m+1)*2+1], n_df3[m*2+1]

                    ms_list_t[m], ms_list_t[(m+1)] =ms_list_t[(m+1)] ,ms_list_t[m]

                    m = m + 1

                 if b == m:
                     break

        else:
           self.state[a], self.state[b] = self.state[b], self.state[a]

           #注意：入れ替えできるのはリスト配列だけ
           #工程時間の入れ替え
           ID[a*2] , ID[b*2] = ID[b*2], ID[a*2]
           ID[a*2+1] , ID[b*2+1] = ID[b*2+1], ID[a*2+1]

           #組み立て仕様の入れ替え
           n_df3[a*2] , n_df3[b*2] = n_df3[b*2], n_df3[a*2]
           n_df3[a*2+1] , n_df3[b*2+1] = n_df3[b*2+1], n_df3[a*2+1]
           ms_list_t[a], ms_list_t[b] =ms_list_t[b] ,ms_list_t[a]

           #組み立て仕様の入れ替え2
           n_df5[:,:] = n_df6[ID_maru_a,:]

        #print(a,b)
        n_df2 = n_df4[ID,:]

        

    # 目的関数
    def energy(self):
        #グローバル変数の宣言
        global Time_df
        global Time_df_best
        global Time_df_best_process
        global Time_df_previous
        global Time_df_previous_intermidiate

        global counter_u
##        Time_A =time.time()
        #print(ms_list_t[a[0]], ms_list_t[b[0]],self.state[a[0]],self.state[b[0]])

        #過去の計算結果を記憶
        if cost_update[0] != 1:
           #Time_df_previous = copy.deepcopy(Time_df_previous_intermidiate)
           Time_df_previous_intermidiate = copy.deepcopy(Time_df)
           #Total_estimated_time_previous[0]  = copy.deepcopy(Total_estimated_time_previous_intermidiate[0])
           Total_estimated_time_previous_intermidiate[0] = copy.deepcopy(Total_estimated_time[0])

        #データベースdf_2の0列目以降に工程時間が格納
        j_num1 = 0

        #値の初期化
        Top1_2 = [0,0]#np.zeros(2,np.float64)#,np.int32)

        Tfactor2 = -math.log(self.Tmax / self.Tmin)
        T = self.Tmax * math.exp(Tfactor2 * step_n[0] / self.steps)
        global aaaaa
        aaa = 0
        aaaa = 0
        bbb = 0
        ccc = 0
        ddd = 0
        eee = 0
        fff = 0
        Start_n2 = 0
        
##        #仕様が同じシート同士が入れ替わった場合は計算しない
##        if step_n[0] < 0:# and aaaaa !=1:# or T > 100 and step_n[0] > 0 and aaaaa != 1:
##
##            print("Aleat!")
##            
##        else:

        #若い順番のシートまでの工程計算は前回までの計算結果を使いまわす
        if step_n[0] >  2:
            #print("B",step_n)
            #aaaaa = 1
            if a_g[0] > b_g[0]:
               Start_n = b_g[0]*2
            else:
               Start_n = a_g[0]*2

            if cost_update[0] == 1:
               Time_df = copy.deepcopy(Time_df_previous_intermidiate)
               aaaaa = 1

            Top1_2 = [0,0]#np.zeros(2,np.float64)#チルト工程終了時間

##            count_top2 = 0
##            i = 0
##
##            while count_top2 < 10 and Start_n - i > 0:
##
##                i = i + 1
##
##                if n_df2[Start_n - i,j_num1+5] > 0:
##                    if Top1_2[0] < Time_df[1,Start_n - i,5]:
##                       if Top1_2[1] < Time_df[1,Start_n - i,5]:
##                          Top1_2[0] = Top1_2[1]
##                          Top1_2[1] = Time_df[1,Start_n - i,5]
##                       else:
##                          Top1_2[0] = Time_df[1,Start_n - i,5]
##                     
##                       count_top2 = count_top2 + 1
##
##            i = 0

            for i in range(1,10):

                if n_df2[Start_n - i,j_num1+5] > 0:
                    if Top1_2[0] < Time_df[1,Start_n - i,5]:
                       if Top1_2[1] < Time_df[1,Start_n - i,5]:
                          Top1_2[0] = Top1_2[1]
                          Top1_2[1] = Time_df[1,Start_n - i,5]
                       else:
                          Top1_2[0] = Time_df[1,Start_n - i,5]

 
            Time_df[:,Start_n:len(ms)*2,:] = 0

            if Start_n != 0:
               Time_df[0,Start_n,0] = Time_df[0,Start_n-1,1]
               Time_df[1,Start_n,0] = Time_df[0,Start_n,0] + n_df2[Start_n,j_num1]

            if Start_n ==0:
               Top1_2[0] = Time_df[1,0,5]
               
        else:
                Start_n = 1
                Time_df = np.zeros((2,len(ms)*2,6),np.float64)

        #総工程時間の計算
        #データを入れる箱準備(0が工程時間開始(act),1が工程時間終了(ideal),脚番号,工程順 0:溶接～5:チルト)

        #計算開始

        #溶接工程の2番目までの計算
        Time_df[0,0,0] = 0#元々0が入っているため不要
        Time_df[1,0,0] = n_df2[0,j_num1]
        Time_df[0,1,0] = n_df2[0,j_num1]
        Time_df[1,1,0] = Time_df[1,0,0] + n_df2[1,j_num1]

        #1番目の計算
        for j in range(1,6):
            Time_df[0,0,j] =Time_df[0,0,j-1] + n_df2[0,j_num1+j-1]
            Time_df[1,0,j] =Time_df[0,0,j] + n_df2[0,j_num1+j]

        if Start_n == 1:
           Top1_2[0] = Time_df[1,0,5]

           
        if Lot_set[0] == int(len(ms)/Lot_num)-1 or energy_n[0] == 1:
               
           Last = len(self.state)*2
           
        else:
            
           Last = ((Lot_set[0] + 1) * Lot_num-1)*2 + 10

        #ロットサイズ分だけデータを取りだす
        #Time_df_Lot[:,:,:] = Time_df[:,Lot_set[0] * Lot_num*2:Last,:]
            
        for i in range(max(1,Start_n),Last):#600脚の計算   

          #計算時間の短縮のために、小さいサイズの配列を準備し、値を格納
##          if i-Lot_set[0] * Lot_num*2 >= 0:
##             Time_df_temp1[:] = Time_df_Lot[0,i-Lot_set[0] * Lot_num*2,0:6]#Time_df[0,i,0:6]#np.zeros(6,np.float64)#型を定義すると時間かかる
##             Time_df_temp2[:] = Time_df_Lot[1,i-Lot_set[0] * Lot_num*2,0:6]#Time_df[1,i,0:6]#np.zeros(6,np.float64)#型を定義すると時間かかる
##             Time_df_temp1_m1[:] = Time_df_Lot[0,i-1-Lot_set[0] * Lot_num*2,0:6]#Time_df[0,i-1,0:6]#np.zeros(6,np.float64)#型を定義すると時間かかる
##             Time_df_temp2_m1[:] = Time_df_Lot[1,i-1-Lot_set[0] * Lot_num*2,0:6]#Time_df[1,i-1,0:6]#np.zeros(6,np.float64)#型を定義すると時間かかる
##          else:
           
          Time_df_temp1[:] = Time_df[0,i,0:6]#np.zeros(6,np.float64)#型を定義すると時間かかる
          Time_df_temp2[:] = Time_df[1,i,0:6]#np.zeros(6,np.float64)#型を定義すると時間かかる
          Time_df_temp1_m1[:] = Time_df[0,i-1,0:6]#np.zeros(6,np.float64)#型を定義すると時間かかる
          Time_df_temp2_m1[:] = Time_df[1,i-1,0:6]#np.zeros(6,np.float64)#型を定義すると時間かかる

##          Time_df_temp1[:] = np.zeros(6,np.float64)#型を定義すると時間かかる
##          Time_df_temp2[:] = np.zeros(6,np.float64)#型を定義すると時間かかる
##          Time_df_temp1_m1[:] = np.zeros(6,np.float64)#型を定義すると時間かかる
##          Time_df_temp2_m1[:] = np.zeros(6,np.float64)#型を定義すると時間かかる
##          
          n_df2_temp[:] = n_df2[i,j_num1:j_num1+6]
          
          #2番目の計算（1~2番目のシートはチルト工程が空いているため個別に計算）
          if i == 1:
           #締め付け2工程までの開始、終了時間の計算
           for j in range(1,4):
               #max(Time_df[1,i,j-1],Time_df[0,i-1,j+1])を短縮のためにif文に変更
               if Time_df_temp2[j-1] > Time_df_temp1_m1[j+1]:
                   Time_df_temp1[j] = Time_df_temp2[j-1]
               else:
                   Time_df_temp1[j]  = Time_df_temp1_m1[j+1]
              
               Time_df_temp2[j] = Time_df_temp1[j] + n_df2_temp[j]

           #BK工程の開始、終了時間の計算
           #max(Time_df[1,i,j-1],Time_df[1,i-1,j])を短縮のためにif文に変更
           if Time_df_temp2[3] > Time_df_temp2_m1[4]:
                   Time_df_temp1[4] = Time_df_temp2[3]
           else:
                   Time_df_temp1[4] = Time_df_temp2_m1[4]

           Time_df_temp2[4] = Time_df_temp1[4] + n_df2_temp[4]

           #チルト工程の開始、終了時間の計算
           Time_df_temp1[5] = Time_df_temp2[4]
           Time_df_temp2[5] = Time_df_temp1[5] + n_df2_temp[5]
           
           if Top1_2[0] < Time_df_temp2[5]:
              Top1_2[1] = Time_df_temp2[5]
           else:
              Top1_2[1] = Top1_2[0]
              Top1_2[0] = Time_df_temp2[5]

          #3番目以降の計算（チルト工程が空いているため、1~2番目のシートは個別に計算）
          else:
                    
           #BK工程締め付2工程までの開始、終了時間の計算
           for j in range(1,4):

               #max(Time_df[1,i,j-1],Time_df[0,i-1,j+1])を短縮のためにif文に変更
               if Time_df_temp2[j-1] > Time_df_temp1_m1[j+1]:
                   Time_df_temp1[j] = Time_df_temp2[j-1]
               else:
                   Time_df_temp1[j] = Time_df_temp1_m1[j+1]

               Time_df_temp2[j] = Time_df_temp1[j] + n_df2_temp[j]

##           Time_df_temp1[1] = max(Time_df_temp1[0] , Time_df_temp1_m1[2])
##           Time_df_temp1[2] = max(Time_df_temp1[1] , Time_df_temp1_m1[3])
##           Time_df_temp1[3] = max(Time_df_temp1[2] , Time_df_temp1_m1[4])
##           Time_df_temp2[1] = Time_df_temp1[1] + n_df2_temp[1]
##           Time_df_temp2[2] = Time_df_temp1[2] + n_df2_temp[2]
##           Time_df_temp2[3] = Time_df_temp1[3] + n_df2_temp[3]

              
           #BK工程まの開始、終了時間の計算（前の順番の脚のチルト工程の有無で開始時間が変わる）
           j = 4
           if n_df2[i-1,j_num1+5] == 0:#前の順番の脚がチルト工程を実施しない場合

               #max(Time_df[1,i,j-1],Time_df[1,i-1,j])#前の順番のBKTエンド工程と比較、を短縮のためにif文に変更、
               if Time_df_temp2[j-1] > Time_df_temp2_m1[j]:
                   Time_df_temp1[j] = Time_df_temp2[j-1]
               else:
                   Time_df_temp1[j] = Time_df_temp2_m1[j]

               Time_df_temp2[j] = Time_df_temp1[j] + n_df2_temp[j]

           else:
               #max(Time_df[1,i,j-1],Time_df[0,i-1,j+1])を短縮のためにif文に変更
               if Time_df_temp2[j-1] > Time_df_temp1_m1[j+1]:
                   Time_df_temp1[j] = Time_df_temp2[j-1]
               else:
                   Time_df_temp1[j] = Time_df_temp1_m1[j+1]

               Time_df_temp2[j] = Time_df_temp1[j] + n_df2_temp[j]

               
           #チルト工程の開始、終了時間の計算
           if n_df2_temp[5] == 0:#チルト工程を実施しない場合

              Time_df_temp1[5] = Time_df_temp2[4]#チルト工程開始時間はBKT工程終了時間
              Time_df_temp2[5] = Time_df_temp1[5]#チルト工程終了時間はチルト工程開始時間
          
           else:#チルト工程を実施する場合

              #『BKT工程終了時間』と『チルト工程終了時間の遅い順から2番目』を比較して、『BKT工程終了時間』の方が遅い場合
              if Time_df_temp2[4] > Top1_2[0]:#チルト工程終了時間の遅い順から2番目はTop1_2の最小値

                 Time_df_temp1[5] = Time_df_temp2[4]#チルト工程開始時間はBKT工程終了時間
                 Time_df_temp2[5] = Time_df_temp1[5] + n_df2_temp[5]

              #チルト工程終了時間の順序更新
                 if Time_df_temp2[5] > Top1_2[0]:
                     if Time_df_temp2[5] > Top1_2[1]:
                         Top1_2[0] = Top1_2[1]
                         Top1_2[1] = Time_df_temp2[5]
                     else:
                         Top1_2[0] = Time_df_temp2[5]

              #『BKT工程終了時間』と『チルト工程終了時間の遅い順から2番目』を比較して、『BKT工程終了時間』の方が早い場合
              else:
                 Time_df_temp1[5] = Top1_2[0]#チルト工程開始時間はチルト工程終了時間の遅い順から2番目の終了時間
                 Time_df_temp2[5] = Time_df_temp1[5] + n_df2_temp[5]

                 #チルト工程終了時間の順序更新
                 if Time_df_temp2[5] > Top1_2[0]:
                     if Time_df_temp2[5] > Top1_2[1]:
                         Top1_2[0] = Top1_2[1]
                         Top1_2[1] = Time_df_temp2[5]
                     else:
                         Top1_2[0] = Time_df_temp2[5]

           
          #i+1番目の溶接工程の計算
          if i < len(self.state)*2-1:
            Time_df[0,i+1,0] = Time_df_temp1[1]
            Time_df[1,i+1,0] = Time_df[0,i+1,0] + n_df2[i+1,j_num1]

          #Time_df_Lot[0,i-Lot_set[0] * Lot_num*2,0:6] = Time_df_temp1[:]#np.zeros(6,np.float64)#型を定義すると時間かかる
          #Time_df_Lot[1,i-Lot_set[0] * Lot_num*2,0:6] = Time_df_temp2[:]#np.zeros(6,np.float64)#型を定義すると時間かかる
          Time_df[0,i,:] = Time_df_temp1[:]
          Time_df[1,i,:] = Time_df_temp2[:]
        #Time_df[:,Lot_set[0] * Lot_num*2:Last,:] = Time_df_Lot[:,:,:]  
        
        if Lot_set[0] == int(len(ms)/Lot_num)-1:
           Total_estimated_time[0] = max(Time_df[1,len(self.state)*2-1,5],Top1_2[1])
        else:
           Total_estimated_time[0] = max(Time_df[1,Last-1,5],Top1_2[1])
               
        step_n[0]  = step_n[0]  +1
        
        return Total_estimated_time[0] #1番最後の工程の終了時間

#本プログラムのメイン部分
if __name__ == '__main__':

    Time_A =time.time()

    # 初期割当て
    ms_list = ms.values.tolist()
    ms_list_t = []
    ms_list_best = [[""]]*len(ms_list)
    best_energy_list_index = []
    best_energy_list_t = []
    Lot_set[0] = 0

    for i in range(len(ms_list)):
     ms_list_t.append(ms_list[i][0])
    #ms = pd.DataFrame(ms_list_t,columns=['manufacturing_sequence'])
    init_state = ms_list_t

    #SA法の実行を指示する部分

    #Csvファイルに格納するための箱を準備
    FileName = path.splitext(path.basename(__file__))[0]
    ms_csv = pd.DataFrame(ms_list, columns=["INIT"])
    best_energy_list_index.append("INIT")

    #初期コストの代入
    prob = GroupingProblem(init_state)   
    energy_n[0] = 1
    best_energy_list_t.append(prob.energy())
    energy_n[0] = 0
    print(best_energy_list_t[0])

    #n数回実行する
    for n in range(num_repeat):

       ms_n = np.arange(0,len(ms)*2).reshape((len(ms)*2,1))#データを入れる箱の準備
       ms_df= pd.DataFrame(ms_n, columns=["manufacturing_sequence"])#データベース型に変換（VlookUp機能を使えるようにするため）
       ms_df['manufacturing_sequence_s'] = ms_df['manufacturing_sequence'].astype(str)#データを文字型に変換（VlookUp機能を使えるようにするため）

       #シートをRHとLHに分離
       for i in range(len(ms)):
           ms_df.iat[i*2,1] = ms.iat[i,0] + "RH"
           ms_df.iat[i*2+1,1] = ms.iat[i,0]+ "LH"

       #VlookUpでデータを結合
       df1 = pd.merge(ms_df, id_flame , how="left", left_on="manufacturing_sequence_s", right_on="ID+Hand")
       df1_2 = pd.merge(df1 , cycletime , how="left", left_on="ID_RH", right_on="ID")
       df1_3 = pd.merge(ms , id_maru_a , how="left", left_on="manufacturing_sequence", right_on="ID")
       df2 = df1_2.iloc[:, 15:22]
       df3 = df1_2.iloc[:, 8]
       df4 = df1_3.iloc[:, 2:8] * maru_a_replace

       #計算を高速化するためにDataframeからNumpy配列に変換
       n_df2 = df2.values
       n_df3 = df3.values
       n_df4 = df2.values
       n_df5 = df4.values
       n_df6 = df4.values
       n_df7 = df4.values

       for m in range(0,len(n_df5)):
        n_df5[m,5] = (n_df5[m,0] * 10000 +
                    n_df5[m,1] * 1000 +
                    n_df5[m,2] * 100 +
                    n_df5[m,3] * 10 +
                    n_df5[m,4] * 1)

       n_df6 = copy.deepcopy(n_df5)
       n_df7 = copy.deepcopy(n_df5)
 
       #計算を高速化するために整数化
       #n_df2  = n_df2 *100
       #n_df4  = n_df4 *100
       #n_df2 .astype(int)
       n_df2.astype(np.float64)
       n_df4.astype(np.float64)

       n_df5_temp1 = np.zeros(len(n_df5[0,:]),np.float64)
       n_df5_temp2 = np.zeros(len(n_df5[0,:]),np.float64)
       n_df5_temp3 = np.zeros(len(n_df5[0,:]),np.float64)
       n_df5_temp4 = np.zeros(len(n_df5[0,:]),np.float64)

       ID = list(range(len(ms)*2))

       ID_maru_a = list(range(len(ms)))

       #データを入れる箱
       Time_df = np.zeros((2,len(ms)*2,6),np.float64)
       Time_df_previous = np.zeros((2,len(ms)*2,6),np.float64)
       Time_df_previous_intermidiate = np.zeros((2,len(ms)*2,6),np.float64)
       Time_df_best_process = np.zeros((2,len(ms)*2,6),np.float64)
       Time_df_best = np.zeros((2,len(ms)*2,6),np.float64)#np.zeros((2,len(ms)*2,6))

       #チルト工程終了時間の遅い順から2つ
       Top1_2 = np.zeros(2,np.float64)#,np.int32)

       #入れ替え番号
       a_g = np.zeros(1,np.int32)
       b_g = np.zeros(1,np.int32)

       #コスト関数のアップデートの判定を記録するためのフラグ
       cost_update = np.zeros(1,np.int32)

       #ステップ数
       step_n = np.zeros(1,np.int32)

       #総工程時間の格納場所
       Total_estimated_time = np.zeros(2,np.float64)
       #並び替えのリセット
       ms_list_t = []
       for i in range(len(ms_list)):
           ms_list_t.append(ms_list[i][0])

       for r in range(0,num_rotation):
           
           for i in range(0,int(len(ms)/Lot_num)):
              Time_A =time.time()
              if i == 0 and r == 0:#int(len(ms)/Lot_num)-1:
                 prob = GroupingProblem(init_state)
              else:
                 #シートをRHとLHに分離
                 for l in range(0,len(ms)):
                    ms_df.iat[l*2,1] = prob.best_state[l] + "RH"
                    ms_df.iat[l*2+1,1] = prob.best_state[l]+ "LH"
                    ms2.iat[l,0] = prob.best_state[l]
                    
                 #VlookUpでデータを結合
                 df1 = pd.merge(ms_df, id_flame , how="left", left_on="manufacturing_sequence_s", right_on="ID+Hand")
                 df1_2 = pd.merge(df1 , cycletime , how="left", left_on="ID_RH", right_on="ID")
                 df1_3 = pd.merge(ms2 , id_maru_a , how="left", left_on="manufacturing_sequence", right_on="ID")
                 df2 = df1_2.iloc[:, 15:22]
                 df3 = df1_2.iloc[:, 8]
                 df4 = df1_3.iloc[:, 2:8] * maru_a_replace

                 #計算を高速化するためにDataframeからNumpy配列に変換
                 n_df2 = df2.values
                 n_df3 = df3.values
                 n_df4 = df2.values
                 n_df5 = df4.values
                 n_df6 = df4.values

                 n_df5_temp1 = np.zeros(len(n_df5[0,:]),np.float64)
                 n_df5_temp2 = np.zeros(len(n_df5[0,:]),np.float64)
                 n_df5_temp3 = np.zeros(len(n_df5[0,:]),np.float64)
                 n_df5_temp4 = np.zeros(len(n_df5[0,:]),np.float64)
       
                 for m in range(0,len(n_df5)):
                  n_df5[m,5] = (n_df5[m,0] * 10000 +
                              n_df5[m,1] * 1000 +
                              n_df5[m,2] * 100 +
                              n_df5[m,3] * 10 +
                              n_df5[m,4] * 1)

                 n_df6 = copy.deepcopy(n_df5)
        
                 #計算を高速化するために整数化
                 #n_df2  = n_df2 *100
                 #n_df4  = n_df4 *100
                 n_df2.astype(np.float64)
                 n_df4.astype(np.float64)
                 
                 #並び替えのリセット
                 ID = list(range(len(ms)*2))

                 ID_maru_a = list(range(len(ms)))
                 
                 ms_list_t = prob.best_state

                 #チルト工程終了時間の遅い順から2つ
                 Top1_2 = np.zeros(2,np.float64)#,np.int32)

                 #入れ替え番号
                 a_g = np.zeros(1,np.int32)
                 b_g = np.zeros(1,np.int32)

                 #コスト関数のアップデートの判定を記録するためのフラグ
                 cost_update = np.zeros(1,np.int32)

                 Time_df = np.zeros((2,len(ms)*2,6),np.float64)
                 Time_df_previous = np.zeros((2,len(ms)*2,6),np.float64)
                 Time_df_previous_intermidiate = np.zeros((2,len(ms)*2,6),np.float64)

                 #ステップ数
                 step_n = np.zeros(1,np.int32)

                 #総工程時間の格納場所
                 Total_estimated_time = np.zeros(2,np.float64)

                 prob = GroupingProblem(prob.best_state)

                 energy_n[0] = 1

                 status.append(["END", prob.energy(),"","","",""])

                 energy_n[0] = 0

              prob.steps = int(num_step/(len(ms)/Lot_num))
    ##          prob.Tmax = 10
              prob.copy_strategy = "deepcopy"
              Lot_set[0] = i
              #print(Lot_set[0],i)
              prob.best_state,bbbb,status = prob.anneal()  # 焼きなまし実行（計算推移をCsvに保存するようにライブラリを変更している。)
              #ライブラリを変更しない場合
              #a,b = prob.anneal()

              #status_all.append(status)

              #print(status)


              #print(n_df5[0:20,:])

              print(prob.best_energy)

              print(int((time.time()-Time_A)*1000))
              Time_A =time.time()
       ms_csv_t = pd.Series(prob.best_state)
       ms_csv_t = pd.DataFrame(ms_csv_t,columns=['n' + str(n+1)])
       ms_csv = pd.concat([ms_csv, ms_csv_t], axis=1)

       FileNameCsv = FileName + "_n" + str(n+1) + ".csv"

       #Csvファイルに格納
       status_csv = pd.DataFrame(status, columns=["Temperature","Energy","Accept","Improve","Elapsed","Remaining"])
       FileName_status_csv = FileName + "_status_n" + str(n+1) +  ".csv"
       status_csv.to_csv(path.join(path.dirname(__file__), "Status", FileName_status_csv))

       status =[]

       best_energy_list_t.append(prob.best_energy)
       #print(best_energy_list_t)
       best_energy_list_index.append('n' + str(n+1))
       

    #Csvファイルに格納
    ms_csv.to_csv(path.join(path.dirname(__file__), 'Sequense' , FileNameCsv))

    best_energy_list_t2 = pd.Series(best_energy_list_t,index=best_energy_list_index)
    best_energy_list_t2 = pd.DataFrame(best_energy_list_t2,columns=['Best energy'])
    FileName_best_energy_csv = FileName + "_energy_n" + str(n+1) +  ".csv"
    best_energy_list_t2.to_csv(path.join(path.dirname(__file__), 'Energy' , FileName_best_energy_csv))
    #print(best_energy_list_t2)

    print(int((time.time()-Time_A)*1000))
    Time_A =time.time()
