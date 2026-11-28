export function formatExpiry(iso) {
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function initialsFromName(name) {
  return (name || '').split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase();
}
