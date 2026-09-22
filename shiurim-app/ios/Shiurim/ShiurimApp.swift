import SwiftUI

@main
struct ShiurimApp: App {
    @StateObject private var store = RecordingsStore()
    @StateObject private var player = PlayerManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
                .environmentObject(player)
                .environment(\.layoutDirection, .rightToLeft)
        }
    }
}