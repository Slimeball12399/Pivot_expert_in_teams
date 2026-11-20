// MOCK backend (device registration/pairing, SCRUM-151) doesn't
// exist yet. Swap these for real API calls later

let mockBoards = [
  { id: 'PV-0142', location: 'Studio A', status: 'online', wifiName: 'Studio-WiFi', lastSeen: null },
  { id: 'PV-0139', location: 'Studio B', status: 'in_session', wifiName: 'Studio-WiFi', lastSeen: null },
  { id: 'PV-0157', location: 'Travel kit', status: 'online', wifiName: 'Pivot-Hotspot', lastSeen: null },
  { id: 'PV-0101', location: 'Office', status: 'offline', wifiName: null, lastSeen: '2 days ago on Office-Net' },
];

const MOCK_NETWORKS = [
  { ssid: 'Studio-WiFi', security: 'Secured', signal: 'strong' },
  { ssid: 'SDU-Guest', security: 'Open', signal: 'good' },
  { ssid: 'eduroam', security: 'Enterprise login, not supported', signal: 'good', disabled: true },
  { ssid: 'Printer-3F', security: 'Secured', signal: 'weak' },
];

function delay(ms = 900) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function fetchBoards() {
  await delay(500);
  return mockBoards;
}

// Step 1: Bluetooth scan for nearby boards.
export async function scanForBoards() {
  await delay(1800);
  const alreadyPaired = mockBoards[0]; // PV-0142, to show the "already on your account" row
  return {
    newBoard: { id: 'PV-0163', signal: 'strong' },
    alreadyPaired: { id: alreadyPaired.id, location: alreadyPaired.location },
  };
}

export async function fetchWifiNetworks() {
  await delay(700);
  return MOCK_NETWORKS;
}

// Step 2: send the chosen network + password to the board over Bluetooth.
export async function sendWifiToBoard(boardId, ssid) {
  await delay(1400);
  return {
    boardId,
    ssid,
  };
}

// Step 3: the board's own post-setup checklist.
export async function checkBoardHealth(boardId, ssid) {
  await delay(1600);
  return {
    bluetooth: true,
    wifi: ssid,
    server: true,
    sensors: '4 of 4 working',
  };
}

export async function addBoard(boardId, location) {
  await delay(500);
  mockBoards = [...mockBoards, { id: boardId, location, status: 'online', wifiName: null, lastSeen: null }];
  return mockBoards.find((board) => board.id === boardId);
}

export async function updateBoardWifi(boardId, ssid) {
  await delay(1000);
  mockBoards = mockBoards.map((board) => (board.id === boardId ? { ...board, wifiName: ssid } : board));
  return mockBoards.find((board) => board.id === boardId);
}

export async function removeBoard(boardId) {
  await delay(600);
  mockBoards = mockBoards.filter((board) => board.id !== boardId);
}

// Calibration: one measurement per direction, after holding still.
export async function measureCalibrationStep(boardId, direction) {
  await delay(1600);
  const angles = { left: 12.4, right: 12.1, front: 34.8, back: 33.9 };
  return {
    direction,
    stopAngle: angles[direction],
  };
}

export async function saveCalibration(boardId) {
  await delay(600);
  return {
    boardId,
    calibratedAt: new Date().toISOString(),
  };
}
