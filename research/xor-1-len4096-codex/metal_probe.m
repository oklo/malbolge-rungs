#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

int main(void) {
    @autoreleasepool {
        id<MTLDevice> d = MTLCreateSystemDefaultDevice();
        if (!d) return 1;
        MTLSize mt = d.maxThreadsPerThreadgroup;
        printf("device=%s\n", d.name.UTF8String);
        printf("max_threads_per_threadgroup=%lu,%lu,%lu\n",
               (unsigned long)mt.width,(unsigned long)mt.height,(unsigned long)mt.depth);
        printf("max_threadgroup_memory=%lu\n",(unsigned long)d.maxThreadgroupMemoryLength);
        if (@available(macOS 10.13, *))
            printf("recommended_working_set=%llu\n",d.recommendedMaxWorkingSetSize);
    }
    return 0;
}
