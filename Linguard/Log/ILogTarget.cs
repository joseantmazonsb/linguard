namespace Linguard.Log; 

public interface ILogTarget {
    void WriteLine(string message);
}