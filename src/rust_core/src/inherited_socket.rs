use std::{
    io::ErrorKind,
    net::{SocketAddr, UdpSocket},
};
use ggrs::{Message, NonBlockingSocket};

const RECV_BUFFER_SIZE: usize = 4096;

/// 包裝一個已綁定的 UdpSocket，讓 GGRS 可以重用在啟動器中執行 STUN 探測和打洞循環
/// 的相同作業系統 socket。這可保留 NAT 的端口對應（port mapping）從端到端不變，
/// 在對稱 NAT (symmetric NAT) 的情況下這是必要的，因為每次新的 socket 綁定
/// 都會獲得不同的外部端口。
pub struct InheritedSocket {
    socket: UdpSocket,
    buffer: [u8; RECV_BUFFER_SIZE],
}

impl InheritedSocket {
    /// 從啟動器進程透過 `BATTLELITE_SOCK_FD` 環境變數傳遞過來的原始 handle/fd
    /// 重建一個 `UdpSocket`。
    ///
    /// 安全性：`fd` 必須是屬於此程序的有效且開啟中的 UDP socket handle
    ///（透過 os.set_inheritable 並使用 close_fds=False 繼承）。
    pub fn from_fd(fd: usize) -> Result<Self, std::io::Error> {
        #[cfg(windows)]
        let socket = unsafe {
            use std::os::windows::io::{FromRawSocket, RawSocket};
            UdpSocket::from_raw_socket(fd as RawSocket)
        };
        #[cfg(not(windows))]
        let socket = unsafe {
            use std::os::unix::io::{FromRawFd, RawFd};
            UdpSocket::from_raw_fd(fd as RawFd)
        };

        socket.set_nonblocking(true)?;
        Ok(Self { socket, buffer: [0; RECV_BUFFER_SIZE] })
    }
}

impl NonBlockingSocket<SocketAddr> for InheritedSocket {
    fn send_to(&mut self, msg: &Message, addr: &SocketAddr) {
        let buf = bincode::serialize(msg).unwrap();
        self.socket.send_to(&buf, addr).unwrap();
    }

    fn receive_all_messages(&mut self) -> Vec<(SocketAddr, Message)> {
        let mut received = Vec::new();
        loop {
            match self.socket.recv_from(&mut self.buffer) {
                Ok((n, src)) => {
                    if let Ok(msg) = bincode::deserialize(&self.buffer[..n]) {
                        received.push((src, msg));
                    }
                }
                Err(ref e) if e.kind() == ErrorKind::WouldBlock => return received,
                Err(ref e) if e.kind() == ErrorKind::ConnectionReset => continue,
                Err(e) => panic!("{:?}: {} on {:?}", e.kind(), e, &self.socket),
            }
        }
    }
}
