🛡️ StegoLab: Secure Image Steganography

Aplikasi web berbasis Flask untuk menyembunyikan pesan rahasia di dalam citra digital (PNG/BMP) menggunakan kombinasi enkripsi AES-GCM dan teknik penyisipan Least Significant Bit (LSB) Pseudorandom berbasis stego-key.

👥 Tim Pengembang
    Alifia Indah Balkis (247006111103)
    Ahmad Taufik Rafly (247006111106)
    Sopi Anggraeni (247006111121)

---

✨ Fitur Utama
    1. Penyisipan & Ekstraksi: Menyembunyikan dan mengambil kembali pesan rahasia menggunakan metode LSB pada citra PNG dan BMP.
    2. Enkripsi Kuat: Mengamankan pesan menggunakan AES-GCM dengan derivasi kunci PBKDF2-HMAC SHA-256.
    3. Pseudorandom Embedding: Posisi bit diacak menggunakan *Pseudo-Random Number Generator* (PRNG) berdasarkan stego-key sehingga ekstraksi wajib menggunakan kunci yang sama.
    4. Manajemen & Kapasitas:Menyertakan header metadata payload, perhitungan kapasitas maksimum, serta validasi penolakan pesan jika melebihi batas ukuran gambar.
    5. Metrik Evaluasi & Analisis: Perhitungan otomatis nilai Mean Squared Error (MSE), Peak Signal-to-Noise Ratio (PSNR), perbandingan histogram, dan visualisasi Enhanced LSB Plane.
    6. Pengujian Ketahanan & Unit Test: Dilengkapi fitur pengujian kerapuhan terhadap kompresi JPEG (JPEG re-save) serta pengujian unit menggunakan Pytest.

---

Tautan Akses & Demo
Live Website: https://steganography-mauve.vercel.app
Video Demo (YouTube): https://youtu.be/JqGi23ve7to

---

📖 Cara Menggunakan Aplikasi (Tutorial)

Berikut adalah panduan langkah demi langkah untuk menggunakan aplikasi StegoLab:

1. Membuka Aplikasi
Akses tautan live website yang telah disediakan melalui peramban web (browser) di perangkat Anda.

2. Melakukan Penyisipan Pesan (Encode)
   1. Pilih menu Encode pada halaman utama aplikasi.
   2. Unggah file gambar penampung (cover image) berformat PNG atau BMP.
   3. Masukkan teks atau pesan rahasia yang ingin disembunyikan pada kolom yang tersedia.
   4. Masukkan kata kunci pengaman (Stego-Key) yang nantinya akan digunakan untuk proses dekripsi.
   5. Tentukan jumlah bit LSB yang diinginkan (secara default menggunakan mode 1-bit).
   6. Klik tombol proses/eksekusi. Sistem akan menghasilkan stego image beserta informasi metrik kualitas (MSE dan PSNR) yang dapat diunduh.

3. Melakukan Ekstraksi Pesan (Decode)
   1. Pilih menu Decode pada navigasi atas.
   2. Unggah file stego image yang telah berisi pesan tersembunyi.
   3. Masukkan Stego-Key yang tepat dan sama persis dengan kunci saat proses encode.
   4. Klik tombol ekstraksi pesan. Jika kunci dan file sesuai, sistem akan menampilkan kembali pesan rahasia aslinya secara utuh.

4. Pengujian Tambahan (JPEG Test & Analisis): Anda dapat memanfaatkan fitur tambahan pada aplikasi untuk melihat perbandingan histogram citra, visualisasi bidang LSB, serta menguji ketahanan stego image terhadap kompresi format lossy JPEG (JPEG re-save).
