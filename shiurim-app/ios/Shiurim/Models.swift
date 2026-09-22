import Foundation

struct Recording: Codable, Identifiable, Hashable {
    let id: String
    let title: String
    let topic: String
    let section: String
    let sectionOrder: Int
    let order: Int
    let url: URL
    let year: String
    let firstSeen: String?

    private static let df: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()

    /// Marked "חדש" when first seen within the last 30 days.
    var isNew: Bool {
        guard let fs = firstSeen, let d = Self.df.date(from: fs) else { return false }
        let age = Date().timeIntervalSince(d)
        return age >= 0 && age < 30 * 86400
    }
}