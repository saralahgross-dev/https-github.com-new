import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: RecordingsStore
    @EnvironmentObject var player: PlayerManager
    @State private var searchText = ""
    @State private var selectedYear = "הכל"
    @State private var showFullPlayer = false

    private var yearOptions: [String] {
        ["הכל"] + store.years
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Year filter chips
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(yearOptions, id: \.self) { year in
                            Button {
                                selectedYear = year
                            } label: {
                                Text(year)
                                    .font(.subheadline)
                                    .padding(.horizontal, 14)
                                    .padding(.vertical, 8)
                                    .background(selectedYear == year ? Color.accentColor : Color(.systemGray6))
                                    .foregroundColor(selectedYear == year ? .white : .primary)
                                    .cornerRadius(16)
                            }
                        }
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 8)
                }

                // Recordings grouped by section
                List {
                    ForEach(store.sections(year: selectedYear, search: searchText), id: \.name) { section in
                        Section(header: Text(section.name)) {
                            ForEach(section.recordings) { r in
                                RecordingRow(recording: r)
                            }
                        }
                    }
                }
                .listStyle(.plain)
                .searchable(text: $searchText, prompt: "חיפוש שיעור")

                // Mini player
                if player.current != nil {
                    MiniPlayerView(showFull: $showFullPlayer)
                }
            }
            .navigationTitle("שיעורי קהל ברכת יצחק")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showFullPlayer) {
                FullPlayerView()
            }
        }
    }
}

struct RecordingRow: View {
    @EnvironmentObject var player: PlayerManager
    let recording: Recording

    private var isCurrent: Bool {
        player.current?.id == recording.id
    }

    var body: some View {
        Button {
            player.play(recording)
        } label: {
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(recording.title)
                        .lineLimit(2)
                        .font(.body)
                    if !recording.year.isEmpty {
                        Text(recording.year)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                Spacer()
                if recording.isNew {
                    Text("חדש")
                        .font(.caption2)
                        .bold()
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.red)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
                Image(systemName: isCurrent && player.isPlaying ? "speaker.wave.2.fill" : "play.circle")
                    .foregroundColor(isCurrent ? .accentColor : .secondary)
                    .font(.title3)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

struct MiniPlayerView: View {
    @EnvironmentObject var player: PlayerManager
    @Binding var showFull: Bool

    var body: some View {
        if let r = player.current {
            VStack(spacing: 0) {
                ProgressView(value: player.duration > 0 ? player.elapsed / player.duration : 0)
                    .progressViewStyle(.linear)
                    .tint(.accentColor)
                HStack(spacing: 16) {
                    Button {
                        showFull = true
                    } label: {
                        Text(r.title)
                            .lineLimit(1)
                            .font(.subheadline)
                    }
                    .buttonStyle(.plain)
                    Spacer()
                    Button {
                        player.skip(by: -15)
                    } label: {
                        Image(systemName: "gobackward.15")
                            .font(.title3)
                    }
                    Button {
                        player.toggle()
                    } label: {
                        Image(systemName: player.isPlaying ? "pause.fill" : "play.fill")
                            .font(.title2)
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 10)
                .background(.bar)
            }
        }
    }
}

struct FullPlayerView: View {
    @EnvironmentObject var player: PlayerManager
    @State private var scrubbing = false
    @State private var scrubValue: Double = 0

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Spacer()

                Image(systemName: "book.fill")
                    .font(.system(size: 90))
                    .foregroundColor(.accentColor)
                    .padding(40)
                    .background(Color(.systemGray6))
                    .cornerRadius(24)

                if let r = player.current {
                    Text(r.title)
                        .font(.title3)
                        .bold()
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                    if !r.year.isEmpty {
                        Text(r.year)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                }

                VStack(spacing: 4) {
                    Slider(
                        value: Binding(
                            get: { scrubbing ? scrubValue : player.elapsed },
                            set: { scrubbing = true; scrubValue = $0 }
                        ),
                        in: 0 ... max(player.duration, 1),
                        onEditingChanged: { editing in
                            if !editing {
                                player.seek(to: scrubValue)
                                scrubbing = false
                            }
                        }
                    )
                    HStack {
                        Text(formatTime(player.elapsed))
                        Spacer()
                        Text(formatTime(player.duration))
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                }
                .padding(.horizontal, 32)

                HStack(spacing: 44) {
                    Button {
                        player.skip(by: -15)
                    } label: {
                        Image(systemName: "gobackward.15")
                            .font(.largeTitle)
                    }
                    Button {
                        player.toggle()
                    } label: {
                        Image(systemName: player.isPlaying ? "pause.circle.fill" : "play.circle.fill")
                            .font(.system(size: 72))
                    }
                    Button {
                        player.skip(by: 15)
                    } label: {
                        Image(systemName: "goforward.15")
                            .font(.largeTitle)
                    }
                }

                Button(player.rateLabel) {
                    player.cycleRate()
                }
                .font(.headline)
                .padding(.horizontal, 20)
                .padding(.vertical, 10)
                .background(Color(.systemGray6))
                .cornerRadius(12)

                Spacer()
            }
            .navigationTitle("מנגן כעת")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(RecordingsStore())
        .environmentObject(PlayerManager())
        .environment(\.layoutDirection, .rightToLeft)
}