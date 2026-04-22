## 场景二
任务设定：用已经标定的全局OD两端刚性值，结合各行业状况，拆解出机械和IT行业的分行业刚性值，并结合场景设定重新跑凸优化代码，输出场景二的结果到相应的场景代号子文件夹中。

**居住端（O端）行业相对刚性**：
$$\kappa_s^O = \text{KL}(O_s \| \bar{O}) = \sum_i \frac{O_{i,s}}{M_s^O} \ln \frac{O_{i,s}/M_s^O}{\bar{O}_i/\bar{M}^O}$$

**就业端（D端）行业相对刚性**：
$$\kappa_s^D = \text{KL}(D_s \| \bar{D}) = \sum_j \frac{D_{j,s}}{M_s^D} \ln \frac{D_{j,s}/M_s^D}{\bar{D}_j/\bar{M}^D}$$

其中：
- $O_{i,s}$：TAZ $i$ 上行业 $s$ 的居住人数
- $\bar{O}_i = \sum_s O_{i,s}$：TAZ $i$ 的总居住人数（全行业）
- $M_s^O = \sum_i O_{i,s}$：行业 $s$ 的总居住人数（归一化用）

**物理解释**：
- $\kappa_s^O$ 大：该行业居住分布高度偏离全行业均值 → 空间高度集聚 → **居住端刚性高**
- $\kappa_s^O$ 小：该行业居住分布接近全行业均值 → 空间分散 → **居住端弹性高**


"F:\02_250910_Commute\12-gvc\0409比例拉取结果\general\[主城区]taz4-D端回写后.csv"
"F:\02_250910_Commute\12-gvc\0409比例拉取结果\general\[主城区]taz4-O端回写后.csv"