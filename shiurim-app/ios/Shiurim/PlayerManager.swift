import AVFoundation
import MediaPlayer
import Combine

final class PlayerManager: ObservableObject {
    @Published var current: Recording?
    @Published var isPlaying = false
    @Published var elapsed: Double = 0
    @Published var duration: Double = 0
    @Published var playbackRate: Float = 1.0

    private var player: AVPlayer?
    private var timeObserver: Any?
    private var statusObserver: NSKeyValueObservation?
    private let rates: [Float] = [1.0, 1.25, 1.5, 2.0]

    init() {
        configureSession()
        setupRemoteCommands()
    }

    private func configureSession() {
        do {
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            print("audio session error: \(error)")
        }
    }

    func play(_ recording: Recording) {
        if current?.id == recording.id {
            toggle()
            return
        }
        removeTimeObserver()
        statusObserver = nil
        current = recording
        elapsed = 0
        duration = 0
        let item = AVPlayerItem(url: recording.url)
        statusObserver = item.observe(\.status, options: [.new]) { [weak self] item, _ in
            guard let self else { return }
            if item.status == .readyToPlay {
                let d = item.asset.duration.seconds
                self.duration = d.isFinite ? d : 0
                self.updateNowPlaying()
            }
        }
        player = AVPlayer(playerItem: item)
        player?.rate = playbackRate
        addTimeObserver()
        player?.play()
        isPlaying = true
        updateNowPlaying()
    }

    func toggle() {
        guard player != nil else { return }
        if isPlaying {
            player?.pause()
        } else {
            player?.play()
            player?.rate = playbackRate
        }
        isPlaying.toggle()
        updateNowPlaying()
    }

    func seek(to seconds: Double) {
        guard duration > 0 else { return }
        let clamped = max(0, min(duration, seconds))
        player?.seek(to: CMTime(seconds: clamped, preferredTimescale: 600))
        elapsed = clamped
        updateNowPlaying()
    }

    func skip(by seconds: Double) {
        seek(to: elapsed + seconds)
    }

    func cycleRate() {
        if let i = rates.firstIndex(of: playbackRate) {
            playbackRate = rates[(i + 1) % rates.count]
        } else {
            playbackRate = 1.0
        }
        if isPlaying {
            player?.rate = playbackRate
        }
        updateNowPlaying()
    }

    var rateLabel: String {
        let r = Double(playbackRate)
        return r.truncatingRemainder(dividingBy: 1) == 0 ? "x\(Int(r))" : String(format: "x%.2g", r)
    }

    private func addTimeObserver() {
        let interval = CMTime(seconds: 1, preferredTimescale: 600)
        timeObserver = player?.addPeriodicTimeObserver(forInterval: interval, queue: .main) { [weak self] time in
            self?.elapsed = time.seconds
        }
    }

    private func removeTimeObserver() {
        if let o = timeObserver {
            player?.removeTimeObserver(o)
            timeObserver = nil
        }
    }

    // MARK: - Lock screen / Control Center

    private func updateNowPlaying() {
        guard let r = current else {
            MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
            return
        }
        MPNowPlayingInfoCenter.default().nowPlayingInfo = [
            MPMediaItemPropertyTitle: r.title,
            MPMediaItemPropertyArtist: "שיעורי קהל ברכת יצחק",
            MPNowPlayingInfoPropertyElapsedPlaybackTime: elapsed,
            MPMediaItemPropertyPlaybackDuration: duration,
            MPNowPlayingInfoPropertyPlaybackRate: isPlaying ? playbackRate : 0,
        ]
    }

    private func setupRemoteCommands() {
        let c = MPRemoteCommandCenter.shared()

        c.playCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            if !self.isPlaying { self.toggle() }
            return .success
        }
        c.pauseCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            if self.isPlaying { self.toggle() }
            return .success
        }
        c.togglePlayPauseCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            self.toggle()
            return .success
        }
        c.skipForwardCommand.preferredIntervals = [15]
        c.skipForwardCommand.addTarget { [weak self] _ in
            self?.skip(by: 15)
            return .success
        }
        c.skipBackwardCommand.preferredIntervals = [15]
        c.skipBackwardCommand.addTarget { [weak self] _ in
            self?.skip(by: -15)
            return .success
        }
        c.changePlaybackPositionCommand.addTarget { [weak self] event in
            guard let self,
                  let e = event as? MPChangePlaybackPositionCommandEvent else {
                return .commandFailed
            }
            self.seek(to: e.positionTime)
            return .success
        }
    }
}

func formatTime(_ s: Double) -> String {
    guard s.isFinite, s >= 0 else { return "0:00" }
    let i = Int(s)
    if i >= 3600 {
        return String(format: "%d:%02d:%02d", i / 3600, (i % 3600) / 60, i % 60)
    }
    return String(format: "%d:%02d", i / 60, i % 60)
}