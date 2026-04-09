using OperatorPackage.Core;

namespace OperatorPackage.Backend
{
    public interface IAdaptedIATKAdapter
    {
        ViewRepresentation CreateView(ViewRepresentation view);
        ViewRepresentation UpdateView(ViewRepresentation view, FilterMask mask);
    }
}
