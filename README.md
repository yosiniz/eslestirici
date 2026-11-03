# Otopark Plaka Karşılaştırma Sistemi

Windows ve macOS üzerinde iki Excel/CSV dosyasını kullanıcı tanımlı tek veya çoklu sütun kurallarıyla karşılaştıran PySide6 uygulamasıdır. Kaynak dosyalar salt okunur açılır; uygulamada stok/kapasite/eşzamanlı araç limiti mantığı yoktur.

## Başlıca özellikler

- İstenilen sayıda `Dosya 1 sütunu = Dosya 2 sütunu` kuralı
- Kurallar arasında varsayılan **VE**, isteğe bağlı **VEYA** mantığı
- Farklı sütun adlarını arayüzden eşleştirme
- Sütun bazında otomatik, metin, plaka, parasal/sayısal, tarih ve tarih+saat normalizasyonu
- Türkçe para biçimleri için `Decimal` tabanlı güvenli karşılaştırma
- Boş hücrelerin varsayılan olarak eşleşmemesi
- Varsayılan bire bir eşleştirme; bir satırın ikinci kez kullanılmaması
- Tüm uygun eşleşmeler ve yalnız benzersiz eşleşmeler modları
- Eşleşenler, iki dosyanın eşleşmeyenleri ve kısmi eşleşmeler için ayrı sekmeler
- Kaynak satır numaraları ve eşleşen satırların yan yana görünümü
- Sayfalama, arama, sıralama, çoklu satır seçimi ve taşınabilir kolonlar
- Kural şablonlarını kaydetme, yükleme ve silme
- `.xlsx`, `.xlsm`, `.xls` ve `.csv` kaynak desteği
- Her iki Excel dosyası için bağımsız çalışma sayfası (sheet) seçimi
- İstenilen sayıda Excel/CSV dosyasını seçilen sheet'lerden alt alta birleştirme
- Birleştirmede kolon adlarına göre otomatik hizalama ve eksik kolonları boş bırakma
- Birleşik sonuca isteğe bağlı kaynak dosya, kaynak sheet ve kaynak satır bilgisi ekleme
- Boş/boş olmayan, eşit/eşit değil, karşılaştırma, aralık ve metin filtreleri
- Birden fazla filtreyi VE veya VEYA mantığıyla uygulama
- Toplam, ortalama, medyan, min, max, adet, benzersiz adet, standart sapma ve varyans
- Sıralama, boş doldurma/silme, tekrar kaldırma ve metin biçimlendirme
- Toplama, çıkarma, çarpma, bölme, yüzde, yüzde değişim ve metin birleştirme ile yeni sütun oluşturma
- QThread tabanlı okuma, karşılaştırma, arama ve dışa aktarma
- Biçimlendirilmiş, denetlenebilir beş sayfalı `.xlsx` çıktısı
- Windows ve macOS'ta kullanılan özgün yeşil **Y** uygulama simgesi

## Kullanım

1. **Dosya 1 Seç** ve **Dosya 2 Seç** düğmeleriyle kaynakları seçin.
2. Bir dosyada birden fazla çalışma sayfası varsa dosyanın yanındaki **Sheet** listesinden kullanılacak sayfayı seçin. Her iki dosyanın sayfası ayrı seçilebilir.
3. İlk kural otomatik oluşturulur ve plaka benzeri kolonlar tahmin edilir.
4. Gerekirse kolonları ve veri türünü değiştirin; **+ Yeni Eşleştirme Kuralı Ekle** ile başka kurallar ekleyin.
5. **Ayarlar** düğmesinden harf/boşluk davranışı, boş hücre eşleşmesi ve toleransları belirleyin.
6. VE/VEYA mantığını ve tekrar kayıt modunu seçin.
7. **Karşılaştır** düğmesine basın. Sheet veya kural değişirse sonuç geçersiz kılınır ve yeniden hesaplanır.
8. **Excel Olarak Kaydet** ile yeni bir çıktı oluşturun.

Tek kural seçildiğinde önceki tek sütun eşleştirme kullanım biçimi korunur. Varsayılan bire bir modda adaylar dosyadaki özgün sıra ile deterministik olarak tüketilir.

## Excel çıktısı

Her dışa aktarmada şu sayfalar üretilir:

1. `Eşleşen Veriler`
2. `Dosya 1 Eşleşmeyenler`
3. `Dosya 2 Eşleşmeyenler`
4. `Kısmi Eşleşenler`
5. `Eşleştirme Kuralları ve Özet`

Orijinal sütunlar ve değerler korunur. Eşleşen/kısmi kayıtlarda iki dosyanın satırları yan yana, kaynak Excel satır numaralarıyla yer alır. Başlıklar biçimlendirilir, ilk satır dondurulur ve AutoFilter eklenir.

## Birden fazla Excel'i alt alta birleştirme

Ana ekrandaki **Excel Dosyalarını Birleştir** düğmesine basın:

1. **+ Excel/CSV Ekle** ile iki veya daha fazla dosya seçin.
2. Her dosyanın yanındaki **Sheet** listesinden birleştirilecek çalışma sayfasını belirleyin. Aynı Excel dosyasını yeniden ekleyerek farklı sheet'leri de birleştirebilirsiniz.
3. Dosyaları **Yukarı/Aşağı** düğmeleriyle istediğiniz sıraya getirin.
4. Varsayılan **Kolon adlarına göre hizala** seçeneği, aynı adlı kolonları üst üste getirir; bir dosyada bulunmayan kolonları boş bırakır ve sonradan karşılaşılan yeni kolonları sonuca ekler.
5. İsterseniz bütün dosyalarda aynı kolon sırasını ve adlarını zorunlu tutan katı modu seçin.
6. **Dosyaları Birleştir** ile sonucu önizleyin, arayın ve sıralayın.
7. **Birleşik Exceli Kaydet** ile yeni bir `.xlsx` oluşturun.

Çıktıda `Birleştirilmiş Veriler` ve `Birleştirme Özeti` sayfaları bulunur. Kaynak dosyalar değiştirilmez. Kaynak bilgi kolonları açıksa her satırın geldiği dosya, sheet ve özgün Excel satır numarası sonuçta yer alır.

## Excel işlemleri ve filtreler

Ana ekrandaki **Excel İşlemleri ve Filtreler** düğmesiyle çalışma kopyası üzerinde şu işlemler yapılabilir:

- **Filtreleme:** boş olan, boş olmayan, eşit, eşit değil, büyük/küçük, büyük/küçük veya eşit, iki değer arasında, içerir, içermez, ile başlar, ile biter ve listede bulunan.
- **Çoklu filtre:** kuralları VE veya VEYA mantığıyla birlikte uygulama.
- **Özet hesaplama:** toplam, ortalama, medyan, minimum, maksimum, dolu adet, benzersiz adet, standart sapma ve varyans.
- **Sıralama:** sayı, tarih veya metin kolonunu artan/azalan sıralama.
- **Boş değer:** seçilen kolondaki boş satırları kaldırma veya kullanıcı değerleriyle doldurma.
- **Tekrarlar:** tamamen aynı satırları ya da seçilen kolona göre tekrarları kaldırma; ilk veya son kaydı saklama.
- **Metin:** trim, büyük harf, küçük harf ve başlık biçimi.
- **Yeni sütun:** iki sütun veya bir sabit kullanarak toplama, çıkarma, çarpma, bölme, yüzde ve yüzde değişim; iki metin kolonunu birleştirme.

İşlemler sırayla mevcut sonuç üzerine uygulanır. **Orijinal Veriye Dön** düğmesi yüklenen çalışma kopyasını sıfırlar. **İşlenmiş Exceli Kaydet** her zaman yeni bir `.xlsx` oluşturur; kaynak dosyanın üzerine yazılmaz.

## Proje yapısı

```text
main.py
assets/
  app_icon.png
  app_icon.ico
  app_icon.icns
OtoparkPlakaKontrol.spec
OtoparkPlakaKontrol-OneFile.spec
OtoparkPlakaKontrol-macOS.spec
models/paged_dataframe_model.py
services/
  data_operation_service.py
  excel_service.py
  merge_service.py
  matching_service.py
  export_service.py
  template_service.py
ui/
  data_tools_dialog.py
  main_window.py
  merge_dialog.py
  matching_rules_widget.py
  result_table.py
  styles.py
utils/
  plate_utils.py
  runtime_paths.py
  value_normalizers.py
workers/process_worker.py
scripts/
  build_windows_portable.ps1
  build_macos.sh
tests/
requirements.txt
```

## Kurulum ve çalıştırma

Windows 10/11 veya güncel macOS ile 64 bit Python 3.11/3.12 önerilir.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

PowerShell etkinleştirme betiğini engellerse yalnız mevcut terminal için:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Testler

```powershell
python -m unittest discover -s tests -v
```

Testler tek/çok kural, AND/OR, para/plaka/tarih normalizasyonu, boş değerler, bire bir tekrar tüketimi, tüm eşleşmeler, şablonlar, çoklu Excel birleştirme ve biçimlendirilmiş Excel çıktılarını kapsar.

## Windows EXE oluşturma

Daha hızlı başlangıç ve Qt DLL'lerinin görünür olması nedeniyle `--onedir` önerilir. Projedeki spec dosyası ICU/Qt DLL çakışmasına karşı filtre içerir:

```powershell
.\.venv\Scripts\Activate.ps1
pyinstaller --noconfirm --clean OtoparkPlakaKontrol.spec
```

Çalıştırılabilir dosya:

```text
dist\OtoparkPlakaKontrol\OtoparkPlakaKontrol.exe
```

Genel `--onedir` komutu:

```powershell
pyinstaller --noconfirm --clean --noconsole --onedir --name "OtoparkPlakaKontrol" main.py
```

Tek dosya seçeneği (açılışı daha yavaştır):

```powershell
pyinstaller --noconfirm --clean OtoparkPlakaKontrol-OneFile.spec
```

Tek dosyalı çıktı `dist\Eslestirici-v2.3-Windows-x64.exe` konumunda oluşur. GitHub Releases için bu EXE doğrudan kullanılabilir; ilk açılışı portable klasör sürümünden daha yavaştır.

### Windows portable ZIP

Portable paket Python kurulumu gerektirmez. Ayarlar ve eşleştirme şablonları paketin içindeki `data` klasöründe tutulur. Test, derleme ve ZIP oluşturmayı tek komutta çalıştırabilirsiniz:

```powershell
.\scripts\build_windows_portable.ps1
```

Oluşan dosya:

```text
release\OtoparkPlakaKontrol-Windows-x64-Portable.zip
```

ZIP'i herhangi bir klasöre çıkarıp `OtoparkPlakaKontrol.exe` dosyasını çalıştırın. Uygulamayı ZIP'in içinden doğrudan çalıştırmayın.

## macOS Apple Silicon APP ve DMG yükleyici

PyInstaller hedef işletim sisteminde çalıştırılmalıdır; macOS `.app` veya `.dmg` paketi Windows üzerinde üretilemez. Bir Mac üzerinde:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
bash scripts/build_macos.sh
```

Apple Silicon (M1, M2, M3, M4 ve sonraki M serisi) bir Mac'te betik yerel `arm64` uygulaması üretir. Rosetta gerekmez. Betik yanlış mimarili bir makinede paketleme yapılmasını engeller ve oluşan `.app` paketinin imzasını doğrular.

Betik hem `.app` paketini hem de uygulamayı Applications klasörüne sürükleyerek kurmayı sağlayan DMG dosyasını üretir:

```text
release/OtoparkPlakaKontrol-macOS-arm64.dmg
release/OtoparkPlakaKontrol-macOS-x86_64.dmg
```

- `arm64`: Apple Silicon işlemcili Mac (önerilen indirme)
- `x86_64`: Intel işlemcili Mac

Apple Developer sertifikası verilmezse paket ad-hoc imzalanır. İnternetten indirilen ve notarize edilmemiş pakette macOS ilk açılışta uyarı gösterebilir; uygulamaya sağ tıklayıp **Aç** kullanılabilir. Genel dağıtımda uyarısız açılış için Developer ID ile imzalama ve Apple notarization gerekir. Yerel betik `MACOS_SIGNING_IDENTITY` ortam değişkeni tanımlıysa uygulamayı bu kimlikle imzalar.

## GitHub Actions ile otomatik paketleme

Projede `.github/workflows/build-release.yml` iş akışı bulunur. GitHub'a yükledikten sonra:

1. Repository içindeki **Actions** sekmesini açın.
2. **Portable ve macOS paketleri** iş akışını seçin.
3. **Run workflow** düğmesine basın.
4. Tamamlandığında Windows Portable ZIP, macOS Apple Silicon DMG ve macOS Intel DMG artifact olarak indirilir.

Bir GitHub Release oluşturup üç paketi otomatik eklemek için sürüm etiketi gönderin:

```bash
git tag v2.1.0
git push origin v2.1.0
```

GitHub'ın standart runner etiketleri kullanılır: Windows x64, macOS ARM64 ve macOS Intel. `build`, `dist`, `release`, sanal ortam ve yerel kullanıcı verileri `.gitignore` kapsamındadır.

Yeni ve boş bir GitHub repository oluşturduktan sonra projeyi ilk kez göndermek için:

```bash
git init
git add .
git commit -m "İlk sürüm"
git branch -M main
git remote add origin GITHUB_REPOSITORY_ADRESI
git push -u origin main
```

`GITHUB_REPOSITORY_ADRESI` yerine GitHub'ın oluşturduğu HTTPS veya SSH repository adresini yazın. Yerel `release` klasörü GitHub'a gönderilmez; indirilebilir paketler Actions tarafından üretilir.

## Performans ve güvenlik

- Kaynak dosyalar hiçbir zaman yazılmaz veya değiştirilmez.
- Eşitlik kuralları normalize edilmiş hash indeksleriyle çözülür; hücre çifti bazında tam tarama yapılmaz.
- Bire bir eşleştirmede her sağ satır en fazla bir kez kullanılır.
- Büyük sonuçlar Qt'ye sayfa sayfa verilir.
- Excel yazımı `openpyxl` write-only modunda yapılır.
- `Tüm uygun eşleşmeler` modu kombinasyon patlamasına karşı varsayılan 1.000.000 çift sınırına sahiptir.
- Excel sayfa sınırı başlık dahil 1.048.576 satırdır.
