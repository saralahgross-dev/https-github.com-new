import Foundation

final class RecordingsStore: ObservableObject {
    @Published var recordings: [Recording] = []
    @Published var years: [String] = []

    /// Canonical ascending order of Hebrew years.
    private static let yearOrder = ["תש\"פ", "תשפ\"א", "תשפ\"ב", "תשפ\"ג", "תשפ\"ד", "תשפ\"ה", "תשפ\"ו"]

    init() {
        load()
    }

    private func load() {
        guard let url = Bundle.main.url(forResource: "recordings", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let recs = try? JSONDecoder().decode([Recording].self, from: data) else {
            return
        }
        recordings = recs
        let present = Set(recs.map(\.year)).subtracting([""])
        years = Self.yearOrder.filter { present.contains($0) }
            + present.filter { !Self.yearOrder.contains($0) }.sorted()
    }

    /// Sections (in Drive order) with their recordings, honoring the year filter and search text.
    func sections(year: String, search: String) -> [(name: String, recordings: [Recording])] {
        var recs = recordings
        if year != "הכל" {
            recs = recs.filter { $0.year == year }
        }
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines)
        if !q.isEmpty {
            recs = recs.filter {
                $0.title.localizedCaseInsensitiveContains(q)
                    || $0.topic.localizedCaseInsensitiveContains(q)
            }
        }
        let grouped = Dictionary(grouping: recs, by: \.section)
        return grouped
            .map { (name: $0.key, recordings: $0.value.sorted { $0.order < $1.order },
                    order: $0.value.first?.sectionOrder ?? Int.max) }
            .sorted { $0.order < $1.order }
            .map { ($0.name, $0.recordings) }
    }
}