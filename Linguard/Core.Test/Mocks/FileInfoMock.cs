using System.IO;
using Moq;

namespace Core.Test.Mocks; 

public class FileInfoMock : Mock<FileSystemInfo> {
    public FileInfoMock(string name) {
        SetupGet(o => o.FullName).Returns(name);
    }
}