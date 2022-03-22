namespace Linguard.Web.Services; 

public interface IStateHasChangedNotifierService {
    void Subscribe(EventHandler handler);
    void UnSubscribe(EventHandler handler);
    void Notify();
}