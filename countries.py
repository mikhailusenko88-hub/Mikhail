"""193 страны — члены ООН: (alpha-2 для флага, alpha-3 для подписи)."""
RAW = """af AFG al ALB dz DZA ad AND ao AGO ag ATG ar ARG am ARM au AUS at AUT az AZE bs BHS bh BHR bd BGD
bb BRB by BLR be BEL bz BLZ bj BEN bt BTN bo BOL ba BIH bw BWA br BRA bn BRN bg BGR bf BFA bi BDI cv CPV
kh KHM cm CMR ca CAN cf CAF td TCD cl CHL cn CHN co COL km COM cg COG cd COD cr CRI ci CIV hr HRV cu CUB
cy CYP cz CZE dk DNK dj DJI dm DMA do DOM ec ECU eg EGY sv SLV gq GNQ er ERI ee EST sz SWZ et ETH fj FJI
fi FIN fr FRA ga GAB gm GMB ge GEO de DEU gh GHA gr GRC gd GRD gt GTM gn GIN gw GNB gy GUY ht HTI hn HND
hu HUN is ISL in IND id IDN ir IRN iq IRQ ie IRL il ISR it ITA jm JAM jp JPN jo JOR kz KAZ ke KEN ki KIR
kp PRK kr KOR kw KWT kg KGZ la LAO lv LVA lb LBN ls LSO lr LBR ly LBY li LIE lt LTU lu LUX mg MDG mw MWI
my MYS mv MDV ml MLI mt MLT mh MHL mr MRT mu MUS mx MEX fm FSM md MDA mc MCO mn MNG me MNE ma MAR mz MOZ
mm MMR na NAM nr NRU np NPL nl NLD nz NZL ni NIC ne NER ng NGA mk MKD no NOR om OMN pk PAK pw PLW pa PAN
pg PNG py PRY pe PER ph PHL pl POL pt PRT qa QAT ro ROU ru RUS rw RWA kn KNA lc LCA vc VCT ws WSM sm SMR
st STP sa SAU sn SEN rs SRB sc SYC sl SLE sg SGP sk SVK si SVN sb SLB so SOM za ZAF ss SSD es ESP lk LKA
sd SDN sr SUR se SWE ch CHE sy SYR tj TJK tz TZA th THA tl TLS tg TGO to TON tt TTO tn TUN tr TUR tm TKM
tv TUV ug UGA ua UKR ae ARE gb GBR us USA uy URY uz UZB vu VUT ve VEN vn VNM ye YEM zm ZMB zw ZWE"""
_t = RAW.split()
COUNTRIES = [(_t[i], _t[i + 1]) for i in range(0, len(_t), 2)]
A3 = dict(COUNTRIES)
assert len(COUNTRIES) == 193, len(COUNTRIES)
