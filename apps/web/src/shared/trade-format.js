const koreanTime = new Intl.DateTimeFormat('ko-KR', {
  dateStyle: 'long',
  timeStyle: 'medium',
  timeZone: 'Asia/Seoul',
});

export function formatKoreanTime(value) {
  return koreanTime.format(new Date(value));
}

export function formatSide(value) {
  return value === 'BUY' ? '매수' : '매도';
}

export function formatPrice(value) {
  return `${value.toLocaleString('ko-KR')}원`;
}

export function formatQuantity(value) {
  return `${value.toLocaleString('ko-KR')}주`;
}
