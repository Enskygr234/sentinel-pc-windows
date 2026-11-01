## Sentinel PC – gerçek zamanlı sistem monitörü (Windows 10/11)

CPU, RAM, disk ve ağ kullanımı için canlı göstergeler ve grafikler, çekirdek başına kullanım, disk bölümleri ve klasör boyutu
analizi, ağ adaptörleri, onaylı işlem sonlandırma, sistem bilgisi (Windows, işlemci, anakart, BIOS, ekran kartı),
CPU/RAM geçmişi, CSV dışa aktarma ve sistem raporu. Yönetici izni istemez.

| Dosya | Açıklama |
|---|---|
| `SentinelPC-vX.Y.Z.exe` | Tek dosya, kurulum gerektirmez. Geçmiş kayıtları `%LOCALAPPDATA%\SentinelPC` içinde. |
| `SHA256SUMS.txt` | Dosya doğrulama özetleri |

**Sıcaklık:** Yalnızca gerçekten okunabilen sensörler gösterilir. Windows'un standart arabirimlerinden okunamıyorsa
uygulama açıkça "Desteklenmiyor" der ve nedenini açıklar; sahte değer gösterilmez.

**Kod imzası:** EXE imzalı değildir (kod imzalama sertifikası mevcut değil). SmartScreen uyarısında
**Ek bilgi → Yine de çalıştır** seçin; dosyayı `SHA256SUMS.txt` ile doğrulayabilirsiniz.

### Doğrulama
- Çekirdek testleri + gerçek verili ekransız arayüz testi (Windows runner)
- Derlenen EXE `--self-test` ile gerçekten açılıp 10 kontrolden geçirildi (canlı veri, tüm sayfalar, işlem listesi,
  sistem bilgisi, sıcaklık durumu, disk, ağ, geçmiş/CSV/rapor)
