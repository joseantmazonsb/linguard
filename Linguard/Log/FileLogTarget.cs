namespace Linguard.Log; 

public class FileLogTarget : ILogTarget {
    public FileSystemInfo Source { get; }

    public FileLogTarget(FileSystemInfo source) {
        Source = source;
    }

    public void WriteLine(string message) {
        File.AppendAllText(Source.FullName, $"{message}{Environment.NewLine}");
    }

    public override string ToString() {
        return Source.FullName;
    }
}