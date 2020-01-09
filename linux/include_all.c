// it's impossible to actually "include all" headers, it won't compile.
// these cover quite many of the API structs, I believe. feel free to add more!

#include <linux/types.h>
#include <linux/kernel.h>

#include <linux/netdevice.h>
#include <linux/skbuff.h>
#include <linux/net.h>
#include <net/sock.h>
#include <net/protocol.h>

#include <linux/mutex.h>
#include <linux/sched.h>
#include <linux/module.h>
#include <linux/mount.h>
#include <linux/fs.h>

#include <linux/ip.h>
#include <linux/tcp.h>

#include <linux/ftrace.h>
