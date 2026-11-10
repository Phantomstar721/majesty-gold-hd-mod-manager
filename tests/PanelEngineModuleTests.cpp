// Data-only ABI fixture: no module entrypoint or native game provider runs.
#include "../runtime/PanelEngineModules.h"
#include <cassert>
#include <fstream>
#include <iterator>
#include <vector>
int main(int argc,char** argv) {
    using namespace PanelEngineModules;
    assert(argc==7);
    for (unsigned branch=0;branch<3;++branch) for(unsigned service=1;service<=2;++service) {
        std::ifstream stream(argv[1+branch*2+service-1],std::ios::binary);
        std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(stream)),{});
        assert(!bytes.empty());
        assert(ValidDescriptor(bytes.data(),static_cast<unsigned>(bytes.size()),service,branch));
        assert(!ValidDescriptor(bytes.data(),static_cast<unsigned>(bytes.size()),service,(branch+1)%3));
        assert(!ValidDescriptor(bytes.data(),static_cast<unsigned>(bytes.size()),3-service,branch));
        assert(!ValidDescriptor(bytes.data(),255,service,branch));
        const unsigned corruptions[]={0,20,56,68,88,156,200,256};
        for (unsigned offset:corruptions) {
            bytes[offset]^=1;
            assert(!ValidDescriptor(bytes.data(),static_cast<unsigned>(bytes.size()),service,branch));
            bytes[offset]^=1;
        }
    }
}
