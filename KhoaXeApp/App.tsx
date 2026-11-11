import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, Switch, SafeAreaView, StatusBar, ScrollView, TextInput, TouchableOpacity, Image, Alert } from 'react-native';
import { ref, onValue, set, remove } from 'firebase/database';
import { db } from './firebaseConfig';

export default function App() {
  // 1. States cho Cấu hình & Thống kê
  const [choTrong, setChoTrong] = useState(0);
  const [tongCho, setTongCho] = useState(0);
  const [nguongCon, setNguongCon] = useState(0);
  const [inputNguong, setInputNguong] = useState('');
  const [inputTongCho, setInputTongCho] = useState('');
  const [gateInOpen, setGateInOpen] = useState(false);
  const [gateOutOpen, setGateOutOpen] = useState(false);

  // 2. States cho Dữ liệu mảng (Lịch sử & Danh sách đen)
  const [danhSachDen, setDanhSachDen] = useState<string[]>([]);
  const [lichSu, setLichSu] = useState<any[]>([]);

  useEffect(() => {
    // Lắng nghe Cấu Hình
    const configRef = ref(db, 'CauHinh');
    const unsubConfig = onValue(configRef, (snapshot) => {
      if (snapshot.exists()) {
        const data = snapshot.val();
        setChoTrong(data.ChoTrong || 0);
        setTongCho(data.TongCho || 0);
        setNguongCon(data.NguongCon || 0);
        setGateInOpen(data.MoCongInKhuan || false);
        setGateOutOpen(data.MoCongOutKhuan || false);
      }
    });

    // Lắng nghe Danh Sách Đen
    const blackListRef = ref(db, 'DanhSachDen');
    const unsubBlackList = onValue(blackListRef, (snapshot) => {
      if (snapshot.exists()) {
        setDanhSachDen(Object.keys(snapshot.val()));
      } else {
        setDanhSachDen([]);
      }
    });

    // Lắng nghe Lịch Sử Vi Phạm
    const viPhamRef = ref(db, 'ViPham');
    const unsubViPham = onValue(viPhamRef, (snapshot) => {
      if (snapshot.exists()) {
        const data = snapshot.val();
        // Đảo ngược mảng để ca vi phạm mới nhất nổi lên đầu
        setLichSu(Object.values(data).reverse());
      } else {
        setLichSu([]);
      }
    });

    // Cleanup khi đóng app
    return () => {
      unsubConfig();
      unsubBlackList();
      unsubViPham();
    };
  }, []);

  // --- CÁC HÀM XỬ LÝ TƯƠNG TÁC ---
  const updateNguong = () => {
    const val = parseInt(inputNguong);
    if (val > 0) {
      set(ref(db, 'CauHinh/NguongCon'), val).then(() => {
        Alert.alert('Thành công', 'Đã cập nhật ngưỡng nồng độ cồn mới!');
        setInputNguong('');
      });
    } else {
      Alert.alert('Lỗi', 'Vui lòng nhập số hợp lệ!');
    }
  };

  const updateTongCho = () => {
    const val = parseInt(inputTongCho);
    if (val > 0) {
      set(ref(db, 'CauHinh/TongCho'), val);
      set(ref(db, 'CauHinh/ChoTrong'), val).then(() => {
        Alert.alert('Thành công', 'Đã thiết lập lại chỗ đỗ xe trong bãi!');
        setInputTongCho('');
      });
    }
  };

  const unlockCard = (uid: string) => {
    Alert.alert('Xác nhận', `Bạn có chắc chắn muốn gỡ phạt và mở khóa cho thẻ ${uid}?`, [
      { text: 'Hủy', style: 'cancel' },
      { text: 'Mở Khóa', onPress: () => remove(ref(db, `DanhSachDen/${uid}`)) }
    ]);
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#111827" />

      <View style={styles.header}>
        <Text style={styles.headerTitle}>SMART PARKING</Text>
        <View style={styles.onlineBadge}>
          <View style={styles.dot} />
          <Text style={styles.onlineText}>Firebase Online</Text>
        </View>
      </View>

      <ScrollView style={styles.scrollArea} showsVerticalScrollIndicator={false}>

        <View style={styles.statsRow}>
          <View style={[styles.statCard, { borderLeftColor: '#22D3EE', borderLeftWidth: 4 }]}>
            <Text style={styles.statLabel}>Chỗ Trống</Text>
            <Text style={styles.statValue}>{choTrong} <Text style={styles.statSub}>/ {tongCho}</Text></Text>
          </View>
          <View style={[styles.statCard, { borderLeftColor: '#F59E0B', borderLeftWidth: 4 }]}>
            <Text style={styles.statLabel}>Thẻ Bị Khóa</Text>
            <Text style={[styles.statValue, { color: '#F59E0B' }]}>{danhSachDen.length}</Text>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>CẤU HÌNH & ĐIỀU KHIỂN</Text>
          <View style={styles.controlBox}>
            <Text style={styles.inputLabel}>Ngưỡng cồn hiện tại: {nguongCon} mg/L</Text>
            <View style={styles.inputRow}>
              <TextInput style={styles.input} placeholder="Nhập ngưỡng mới..." placeholderTextColor="#6B7280" keyboardType="numeric" value={inputNguong} onChangeText={setInputNguong} />
              <TouchableOpacity style={styles.btnPrimary} onPress={updateNguong}>
                <Text style={styles.btnText}>Lưu</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>Thiết lập lại sức chứa bãi:</Text>
            <View style={styles.inputRow}>
              <TextInput style={styles.input} placeholder="Nhập tổng số chỗ..." placeholderTextColor="#6B7280" keyboardType="numeric" value={inputTongCho} onChangeText={setInputTongCho} />
              <TouchableOpacity style={styles.btnSecondary} onPress={updateTongCho}>
                <Text style={styles.btnText}>Reset</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Barie Vào (Khẩn Cấp)</Text>
              <Switch value={gateInOpen} onValueChange={(v) => set(ref(db, 'CauHinh/MoCongInKhuan'), v)} trackColor={{ false: '#374151', true: '#EF4444' }} thumbColor={gateInOpen ? '#fff' : '#9CA3AF'} />
            </View>
            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Barie Ra (Khẩn Cấp)</Text>
              <Switch value={gateOutOpen} onValueChange={(v) => set(ref(db, 'CauHinh/MoCongOutKhuan'), v)} trackColor={{ false: '#374151', true: '#EF4444' }} thumbColor={gateOutOpen ? '#fff' : '#9CA3AF'} />
            </View>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>DANH SÁCH ĐEN (LOCKED)</Text>
          {danhSachDen.length === 0 ? (
            <Text style={styles.emptyText}>Không có thẻ nào bị khóa.</Text>
          ) : (
            danhSachDen.map((uid) => (
              <View key={uid} style={styles.blacklistItem}>
                <View>
                  <Text style={styles.uidText}>{uid}</Text>
                  <Text style={styles.uidSub}>Bị chặn truy cập</Text>
                </View>
                <TouchableOpacity style={styles.btnUnlock} onPress={() => unlockCard(uid)}>
                  <Text style={styles.btnTextUnlock}>Mở Khóa</Text>
                </TouchableOpacity>
              </View>
            ))
          )}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>LỊCH SỬ VI PHẠM ({lichSu.length})</Text>
          {lichSu.length === 0 ? (
            <Text style={styles.emptyText}>Chưa có ca vi phạm nào.</Text>
          ) : (
            lichSu.map((item, index) => (
              <View key={index} style={styles.historyItem}>
                <Image source={{ uri: item.AnhMinhChung || 'https://via.placeholder.com/150' }} style={styles.historyImage} />
                <View style={styles.historyInfo}>
                  <Text style={styles.historyCard}>Thẻ: {item.CCCD || 'N/A'}</Text>
                  <Text style={styles.historyAlco}>{Math.round(item.NongDoCon)} <Text style={{ fontSize: 12, color: '#9CA3AF' }}>mg/L</Text></Text>
                  <View style={styles.tag}>
                    <Text style={styles.tagText}>Đã ghi hình</Text>
                  </View>
                </View>
              </View>
            ))
          )}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// --- CSS STYLESHEET ---
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20, borderBottomWidth: 1, borderBottomColor: '#374151', backgroundColor: '#1F2937' },
  headerTitle: { color: '#F59E0B', fontSize: 20, fontWeight: 'bold', letterSpacing: 1 },
  onlineBadge: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#111827', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 20, borderWidth: 1, borderColor: '#374151' },
  dot: { width: 8, height: 8, backgroundColor: '#10B981', borderRadius: 4, marginRight: 6 },
  onlineText: { color: '#9CA3AF', fontSize: 12, fontWeight: '600' },

  scrollArea: { padding: 15 },

  statsRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 20 },
  statCard: { flex: 1, backgroundColor: '#1F2937', padding: 15, borderRadius: 12, marginHorizontal: 5, shadowColor: '#000', elevation: 2 },
  statLabel: { color: '#9CA3AF', fontSize: 12, fontWeight: 'bold', textTransform: 'uppercase', marginBottom: 5 },
  statValue: { color: '#22D3EE', fontSize: 28, fontWeight: 'bold' },
  statSub: { color: '#6B7280', fontSize: 16 },

  section: { marginBottom: 25 },
  sectionTitle: { color: '#fff', fontSize: 14, fontWeight: 'bold', marginBottom: 10, paddingLeft: 5 },

  controlBox: { backgroundColor: '#1F2937', padding: 15, borderRadius: 12 },
  inputLabel: { color: '#D1D5DB', fontSize: 13, marginBottom: 8, marginTop: 10 },
  inputRow: { flexDirection: 'row', marginBottom: 10 },
  input: { flex: 1, backgroundColor: '#111827', borderWidth: 1, borderColor: '#374151', borderRadius: 8, paddingHorizontal: 15, color: '#fff', marginRight: 10 },
  btnPrimary: { backgroundColor: '#F59E0B', paddingHorizontal: 20, justifyContent: 'center', borderRadius: 8 },
  btnSecondary: { backgroundColor: '#0EA5E9', paddingHorizontal: 20, justifyContent: 'center', borderRadius: 8 },
  btnText: { color: '#111827', fontWeight: 'bold', fontSize: 14 },

  switchRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 15, paddingVertical: 5, borderTopWidth: 1, borderTopColor: '#374151' },
  switchLabel: { color: '#9CA3AF', fontSize: 14, fontWeight: 'bold' },

  blacklistItem: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#1F2937', padding: 15, borderRadius: 10, marginBottom: 10, borderWidth: 1, borderColor: '#451A1A' },
  uidText: { color: '#fff', fontSize: 16, fontWeight: 'bold' },
  uidSub: { color: '#EF4444', fontSize: 12, marginTop: 2 },
  btnUnlock: { backgroundColor: '#374151', paddingHorizontal: 15, paddingVertical: 8, borderRadius: 6, borderWidth: 1, borderColor: '#4B5563' },
  btnTextUnlock: { color: '#D1D5DB', fontSize: 12, fontWeight: 'bold' },

  historyItem: { flexDirection: 'row', backgroundColor: '#1F2937', padding: 15, borderRadius: 10, marginBottom: 10 },
  historyImage: { width: 70, height: 70, borderRadius: 8, marginRight: 15 },
  historyInfo: { flex: 1, justifyContent: 'center' },
  historyCard: { color: '#fff', fontSize: 14, fontWeight: 'bold', marginBottom: 4 },
  historyAlco: { color: '#EF4444', fontSize: 20, fontWeight: 'bold', marginBottom: 6 },
  tag: { backgroundColor: 'rgba(239, 68, 68, 0.2)', alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(239, 68, 68, 0.5)' },
  tagText: { color: '#FCA5A5', fontSize: 10, fontWeight: 'bold' },

  emptyText: { color: '#6B7280', textAlign: 'center', marginVertical: 20, fontStyle: 'italic' }
});