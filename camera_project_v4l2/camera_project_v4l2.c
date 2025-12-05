/*
 * camera_project_v4l2.c
 *
 *  Created on: Mar 12, 2022
 *      Author: steveb
 */

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdbool.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/videodev2.h>
#include <time.h>
#include <sys/mman.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <dirent.h>

#define PRINT_STUFF( VARIABLE, FIELD, MASK ) \
  do \
  { \
    if ((VARIABLE.FIELD & MASK) != 0) \
    { \
      printf( "    " #MASK "\n" ); \
    } \
    else \
    { \
      ; /* does not have the capability */ \
    } \
  } while (0)

static void print_querycap( int fd )
{
  int                     ioctl_result;
  struct v4l2_capability  caps;

  ioctl_result = ioctl( fd, VIDIOC_QUERYCAP, &caps );
  if (ioctl_result >= 0)
  {
    printf( "cap driver: %s\n", caps.driver );
    printf( "cap card:   %s\n", caps.card );
    printf( "cap bus:    %s\n", caps.bus_info );

    printf( "cap capabilities: 0x%8.8X\n", caps.capabilities );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_VIDEO_CAPTURE        );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_VIDEO_OUTPUT         );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_VIDEO_OVERLAY        );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_VBI_CAPTURE          );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_VBI_OUTPUT           );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_SLICED_VBI_CAPTURE   );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_SLICED_VBI_OUTPUT    );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_RDS_CAPTURE          );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_VIDEO_OUTPUT_OVERLAY );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_HW_FREQ_SEEK         );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_RDS_OUTPUT           );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_VIDEO_CAPTURE_MPLANE );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_VIDEO_OUTPUT_MPLANE  );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_VIDEO_M2M_MPLANE     );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_VIDEO_M2M            );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_TUNER                );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_AUDIO                );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_RADIO                );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_MODULATOR            );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_SDR_CAPTURE          );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_EXT_PIX_FORMAT       );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_SDR_OUTPUT           );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_META_CAPTURE         );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_READWRITE            );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_ASYNCIO              );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_STREAMING            );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_META_OUTPUT          );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_TOUCH                );
    PRINT_STUFF( caps, capabilities, V4L2_CAP_DEVICE_CAPS          );
  }
  else
  {
    printf( "ioctl error %d\n", __LINE__ );
  }
  printf( "\n" );

  return;
}

static void print_enuminput( int fd )
{
  int                     ioctl_result;
  uint32_t                index;
  struct v4l2_input       input;

  index = 0;
  input.index = index;
  for (ioctl_result = ioctl( fd, VIDIOC_ENUMINPUT, &input );
      ioctl_result >= 0;
      ioctl_result = ioctl( fd, VIDIOC_ENUMINPUT, &input ))
  {
    printf( "input %2.1d name: %s\n", input.index, input.name );
    switch (input.type)
    {
      case V4L2_INPUT_TYPE_TUNER:   printf( "         type: tuner\n" ); break;
      case V4L2_INPUT_TYPE_CAMERA:  printf( "         type: camera\n" ); break;
      case V4L2_INPUT_TYPE_TOUCH:   printf( "         type: touch\n" ); break;
      default:                      printf( "         type: UNKNOWN\n" ); break;
    }
    printf( "         audio: 0x%8.8X\n", input.audioset );
    printf( "         tuner: 0x%8.8X\n", input.tuner );
    printf( "         std: 0x%16.16llX\n", input.std );
    PRINT_STUFF( input, std, V4L2_STD_PAL_B        );
    PRINT_STUFF( input, std, V4L2_STD_PAL_B1      );
    PRINT_STUFF( input, std, V4L2_STD_PAL_G       );
    PRINT_STUFF( input, std, V4L2_STD_PAL_H       );
    PRINT_STUFF( input, std, V4L2_STD_PAL_I       );
    PRINT_STUFF( input, std, V4L2_STD_PAL_D       );
    PRINT_STUFF( input, std, V4L2_STD_PAL_D1      );
    PRINT_STUFF( input, std, V4L2_STD_PAL_K       );
    PRINT_STUFF( input, std, V4L2_STD_PAL_M       );
    PRINT_STUFF( input, std, V4L2_STD_PAL_N       );
    PRINT_STUFF( input, std, V4L2_STD_PAL_Nc      );
    PRINT_STUFF( input, std, V4L2_STD_PAL_60      );
    PRINT_STUFF( input, std, V4L2_STD_NTSC_M      );
    PRINT_STUFF( input, std, V4L2_STD_NTSC_M_JP   );
    PRINT_STUFF( input, std, V4L2_STD_NTSC_443    );
    PRINT_STUFF( input, std, V4L2_STD_NTSC_M_KR   );
    PRINT_STUFF( input, std, V4L2_STD_SECAM_B     );
    PRINT_STUFF( input, std, V4L2_STD_SECAM_D     );
    PRINT_STUFF( input, std, V4L2_STD_SECAM_G     );
    PRINT_STUFF( input, std, V4L2_STD_SECAM_H     );
    PRINT_STUFF( input, std, V4L2_STD_SECAM_K     );
    PRINT_STUFF( input, std, V4L2_STD_SECAM_K1    );
    PRINT_STUFF( input, std, V4L2_STD_SECAM_L     );
    PRINT_STUFF( input, std, V4L2_STD_SECAM_LC    );
    PRINT_STUFF( input, std, V4L2_STD_ATSC_8_VSB  );
    PRINT_STUFF( input, std, V4L2_STD_ATSC_16_VSB );
    PRINT_STUFF( input, std, V4L2_STD_NTSC        );
    PRINT_STUFF( input, std, V4L2_STD_SECAM_DK    );
    PRINT_STUFF( input, std, V4L2_STD_SECAM       );
    PRINT_STUFF( input, std, V4L2_STD_PAL_BG      );
    PRINT_STUFF( input, std, V4L2_STD_PAL_DK      );
    PRINT_STUFF( input, std, V4L2_STD_PAL         );
    PRINT_STUFF( input, std, V4L2_STD_B           );
    PRINT_STUFF( input, std, V4L2_STD_G           );
    PRINT_STUFF( input, std, V4L2_STD_H           );
    PRINT_STUFF( input, std, V4L2_STD_L           );
    PRINT_STUFF( input, std, V4L2_STD_GH          );
    PRINT_STUFF( input, std, V4L2_STD_DK          );
    PRINT_STUFF( input, std, V4L2_STD_BG          );
    PRINT_STUFF( input, std, V4L2_STD_MN          );
    PRINT_STUFF( input, std, V4L2_STD_MTS         );
    PRINT_STUFF( input, std, V4L2_STD_525_60      );
    PRINT_STUFF( input, std, V4L2_STD_625_50      );
    PRINT_STUFF( input, std, V4L2_STD_ATSC        );
    printf( "         status: 0x%8.8X\n", input.status );
    PRINT_STUFF( input, status, V4L2_IN_ST_NO_POWER     );
    PRINT_STUFF( input, status, V4L2_IN_ST_NO_SIGNAL    );
    PRINT_STUFF( input, status, V4L2_IN_ST_NO_COLOR     );
    PRINT_STUFF( input, status, V4L2_IN_ST_HFLIP        );
    PRINT_STUFF( input, status, V4L2_IN_ST_VFLIP        );
    PRINT_STUFF( input, status, V4L2_IN_ST_NO_H_LOCK    );
    PRINT_STUFF( input, status, V4L2_IN_ST_COLOR_KILL   );
    PRINT_STUFF( input, status, V4L2_IN_ST_NO_V_LOCK    );
    PRINT_STUFF( input, status, V4L2_IN_ST_NO_STD_LOCK  );
    PRINT_STUFF( input, status, V4L2_IN_ST_NO_SYNC      );
    PRINT_STUFF( input, status, V4L2_IN_ST_NO_EQU       );
    PRINT_STUFF( input, status, V4L2_IN_ST_NO_CARRIER   );
    PRINT_STUFF( input, status, V4L2_IN_ST_MACROVISION  );
    PRINT_STUFF( input, status, V4L2_IN_ST_NO_ACCESS    );
    PRINT_STUFF( input, status, V4L2_IN_ST_VTR          );
    printf( "         capabilities: 0x%8.8X\n", input.capabilities );
    PRINT_STUFF( input, capabilities, V4L2_IN_CAP_DV_TIMINGS      );
    PRINT_STUFF( input, capabilities, V4L2_IN_CAP_CUSTOM_TIMINGS  );
    PRINT_STUFF( input, capabilities, V4L2_IN_CAP_STD             );
    PRINT_STUFF( input, capabilities, V4L2_IN_CAP_NATIVE_SIZE     );

    index++;
    input.index = index;
  }
  printf( "\n" );

  return;
}

static void print_format( int fd, struct v4l2_format *format )
{
  int                     ioctl_result;

  /*
   * https://linuxtv.org/downloads/legacy/video4linux/API/V4L2_API/spec-single/v4l2.html
   * section 4.1.3:
   * set the type field in the v4l2_format to V4L2_BUF_TYPE_VIDEO_CAPTURE and call VIDIOC_G_FMT to query the supported image formats
   */
  format->type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  ioctl_result = ioctl( fd, VIDIOC_G_FMT, format );
  if (ioctl_result >= 0)
  {
    printf( "format width:        %u\n", format->fmt.pix.width );
    printf( "format height:       %u\n", format->fmt.pix.height );
    printf( "format pixelformat:  0x%8.8X (%c-%c-%c-%c)\n", format->fmt.pix.pixelformat,
        (format->fmt.pix.pixelformat>> 0)&0xFF,
        (format->fmt.pix.pixelformat>> 8)&0xFF,
        (format->fmt.pix.pixelformat>>16)&0xFF,
        (format->fmt.pix.pixelformat>>24)&0xFF );
    printf( "format field:        0x%8.8X\n", format->fmt.pix.field );
    switch (format->fmt.pix.field)
    {
      case V4L2_FIELD_ANY:            printf( "    V4L2_FIELD_ANY\n" );           break;
      case V4L2_FIELD_NONE:           printf( "    V4L2_FIELD_NONE\n" );          break;
      case V4L2_FIELD_TOP:            printf( "    V4L2_FIELD_TOP\n" );           break;
      case V4L2_FIELD_BOTTOM:         printf( "    V4L2_FIELD_BOTTOM\n" );        break;
      case V4L2_FIELD_INTERLACED:     printf( "    V4L2_FIELD_INTERLACED\n" );    break;
      case V4L2_FIELD_SEQ_TB:         printf( "    V4L2_FIELD_SEQ_TB\n" );        break;
      case V4L2_FIELD_SEQ_BT:         printf( "    V4L2_FIELD_SEQ_BT\n" );        break;
      case V4L2_FIELD_ALTERNATE:      printf( "    V4L2_FIELD_ALTERNATE\n" );     break;
      case V4L2_FIELD_INTERLACED_TB:  printf( "    V4L2_FIELD_INTERLACED_TB\n" ); break;
      case V4L2_FIELD_INTERLACED_BT:  printf( "    V4L2_FIELD_INTERLACED_BT\n" ); break;
      default:                        printf( "    UNKOWN\n" );                   break;
    }
    printf( "format bytesperline: 0x%8.8X\n", format->fmt.pix.bytesperline );
    printf( "format sizeimage:    0x%8.8X\n", format->fmt.pix.sizeimage );
    printf( "format colorspace:   0x%8.8X\n", format->fmt.pix.colorspace );
    switch (format->fmt.pix.colorspace)
    {
      case V4L2_COLORSPACE_DEFAULT:       printf( "    V4L2_COLORSPACE_DEFAULT\n" );        break;
      case V4L2_COLORSPACE_SMPTE170M:     printf( "    V4L2_COLORSPACE_SMPTE170M\n" );      break;
      case V4L2_COLORSPACE_SMPTE240M:     printf( "    V4L2_COLORSPACE_SMPTE240M\n" );      break;
      case V4L2_COLORSPACE_REC709:        printf( "    V4L2_COLORSPACE_REC709\n" );         break;
      case V4L2_COLORSPACE_BT878:         printf( "    V4L2_COLORSPACE_BT878\n" );          break;
      case V4L2_COLORSPACE_470_SYSTEM_M:  printf( "    V4L2_COLORSPACE_470_SYSTEM_M\n" );   break;
      case V4L2_COLORSPACE_470_SYSTEM_BG: printf( "    V4L2_COLORSPACE_470_SYSTEM_BG\n" );  break;
      case V4L2_COLORSPACE_JPEG:          printf( "    V4L2_COLORSPACE_JPEG\n" );           break;
      case V4L2_COLORSPACE_SRGB:          printf( "    V4L2_COLORSPACE_SRGB\n" );           break;
      case V4L2_COLORSPACE_OPRGB:         printf( "    V4L2_COLORSPACE_OPRGB\n" );          break;
      case V4L2_COLORSPACE_BT2020:        printf( "    V4L2_COLORSPACE_BT2020\n" );         break;
      case V4L2_COLORSPACE_RAW:           printf( "    V4L2_COLORSPACE_RAW\n" );            break;
      case V4L2_COLORSPACE_DCI_P3:        printf( "    V4L2_COLORSPACE_DCI_P3\n" );         break;
      default:                            printf( "    UNKNOWN\n" );                        break;
    }
  }
  else
  {
    printf( "ioctl error %d\n", __LINE__ );
  }
  printf( "\n" );

  return;
}

static void print_enum_fmt_and_framesizes( int fd )
{
  int                     ioctl_result;
  uint32_t                index_fmt;
  struct v4l2_fmtdesc     fmtdesc;
  uint32_t                index_frmsizeenum;
  struct v4l2_frmsizeenum frmsizeenum;

  index_fmt = 0;
  fmtdesc.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  fmtdesc.index = index_fmt;
  for (ioctl_result = ioctl( fd, VIDIOC_ENUM_FMT, &fmtdesc );
      ioctl_result >= 0;
      ioctl_result = ioctl( fd, VIDIOC_ENUM_FMT, &fmtdesc ))
  {
    printf( "fmt[%2.1d] desc: %s\n",          fmtdesc.index, fmtdesc.description );
    printf( "        flags: 0x%8.8X\n",       fmtdesc.flags );
    printf( "        pixelformat: 0x%8.8X (%c-%c-%c-%c)\n", fmtdesc.pixelformat,
        (fmtdesc.pixelformat>> 0)&0xFF,
        (fmtdesc.pixelformat>> 8)&0xFF,
        (fmtdesc.pixelformat>>16)&0xFF,
        (fmtdesc.pixelformat>>24)&0xFF );

    index_frmsizeenum = 0;
    frmsizeenum.index = index_frmsizeenum;
    frmsizeenum.pixel_format = fmtdesc.pixelformat;
    for (ioctl_result = ioctl( fd, VIDIOC_ENUM_FRAMESIZES, &frmsizeenum );
        ioctl_result >= 0;
        ioctl_result = ioctl( fd, VIDIOC_ENUM_FRAMESIZES, &frmsizeenum ))
    {
      printf( "        size[%2.1d] pixel_format: 0x%8.8X\n", frmsizeenum.index, frmsizeenum.pixel_format );
      switch (frmsizeenum.type)
      {
        case V4L2_FRMSIZE_TYPE_DISCRETE:
          printf( "                 type: DISCRETE\n" );
          printf("                  width:  %d\n", frmsizeenum.discrete.width );
          printf("                  height: %d\n", frmsizeenum.discrete.height );
          break;
        case V4L2_FRMSIZE_TYPE_CONTINUOUS:
          printf( "                 type: CONTINUOUS\n" );
          break;
        case V4L2_FRMSIZE_TYPE_STEPWISE:
          printf( "                 type: STEPWISE\n" );
          printf("                  min_width:   %d\n", frmsizeenum.stepwise.min_width   );
          printf("                  max_width:   %d\n", frmsizeenum.stepwise.max_width   );
          printf("                  step_width:  %d\n", frmsizeenum.stepwise.step_width  );
          printf("                  min_height:  %d\n", frmsizeenum.stepwise.min_height  );
          printf("                  max_height:  %d\n", frmsizeenum.stepwise.max_height  );
          printf("                  step_height: %d\n", frmsizeenum.stepwise.step_height );
          break;
        default:
          printf( "                 type: UNKNOWN\n" );
          break;
          index_fmt++;
          fmtdesc.index = index_fmt;
      }

      index_frmsizeenum++;
      frmsizeenum.index = index_frmsizeenum;
    }

    index_fmt++;
    fmtdesc.index = index_fmt;
  }
  printf( "\n" );

  return;
}

static void print_frameintervals( int fd )
{
  int                     ioctl_result;
  uint32_t                index_fmt;
  struct v4l2_frmivalenum frame_interval;

  index_fmt = 0;
  frame_interval.index        = index_fmt;
  frame_interval.pixel_format = 0x33424752;
  frame_interval.width        = 1024;
  frame_interval.height       = 768;
  for (ioctl_result = ioctl( fd, VIDIOC_ENUM_FRAMEINTERVALS, &frame_interval );
      ioctl_result >= 0;
      ioctl_result = ioctl( fd, VIDIOC_ENUM_FRAMEINTERVALS, &frame_interval ))
  {
    printf( "frameinterval[%2.1d]\n", index_fmt );
    switch (frame_interval.type)
    {
      case V4L2_FRMIVAL_TYPE_DISCRETE:
        printf( "    discrete=%d/%d\n",
            frame_interval.discrete.numerator, frame_interval.discrete.denominator );
        break;
      case V4L2_FRMIVAL_TYPE_CONTINUOUS:
        printf( "    continuous min=%d/%d, max=%d/%d, step=%d/%d\n",
            frame_interval.stepwise.min.numerator, frame_interval.stepwise.min.denominator,
            frame_interval.stepwise.max.numerator, frame_interval.stepwise.max.denominator,
            frame_interval.stepwise.step.numerator, frame_interval.stepwise.step.denominator );
        break;
      case V4L2_FRMIVAL_TYPE_STEPWISE:
      default:
        printf( "    stepwise min=%d/%d, max=%d/%d, step=%d/%d\n",
            frame_interval.stepwise.min.numerator, frame_interval.stepwise.min.denominator,
            frame_interval.stepwise.max.numerator, frame_interval.stepwise.max.denominator,
            frame_interval.stepwise.step.numerator, frame_interval.stepwise.step.denominator );
        break;
    }

    index_fmt++;
    frame_interval.index = index_fmt;
  }
  printf( "\n" );

  return;
}

/*
static void print_time_difference( struct timespec *start_time, struct timespec *end_time )
{
  time_t diff_seconds;
  long   diff_nanoseconds;

  diff_seconds      = end_time->tv_sec  - start_time->tv_sec;
  diff_nanoseconds  = end_time->tv_nsec - start_time->tv_nsec;

  printf( "elapsed time: %lldus\n", (((long long)diff_seconds) * 1000 * 1000 *1000 + ((long long)diff_nanoseconds)) / 1000 );

  return;
}
*/

#if 0
const char * v4l2_buf_type_to_string( enum v4l2_buf_type buf_type )
{
    const char * return_value;

    switch (buf_type)
    {
      case V4L2_BUF_TYPE_VIDEO_CAPTURE:        return_value = "VIDEO_CAPTURE"; break;
      case V4L2_BUF_TYPE_VIDEO_OUTPUT:         return_value = "VIDEO_OUTPUT"; break;
      case V4L2_BUF_TYPE_VIDEO_OVERLAY:        return_value = "VIDEO_OVERLAY"; break;
      case V4L2_BUF_TYPE_VBI_CAPTURE:          return_value = "VBI_CAPTURE"; break;
      case V4L2_BUF_TYPE_VBI_OUTPUT:           return_value = "VBI_OUTPUT"; break;
      case V4L2_BUF_TYPE_SLICED_VBI_CAPTURE:   return_value = "SLICED_VBI_CAPTURE"; break;
      case V4L2_BUF_TYPE_SLICED_VBI_OUTPUT:    return_value = "SLICED_VBI_OUTPUT"; break;
      case V4L2_BUF_TYPE_VIDEO_OUTPUT_OVERLAY: return_value = "VIDEO_OUTPUT_OVERLAY"; break;
      case V4L2_BUF_TYPE_PRIVATE:              return_value = "PRIVATE"; break;
      default:                                 return_value = "unknown"; break;
    }

    return return_value;
}
const char * v4l2_field_to_string( enum v4l2_field field )
{
    const char * return_value;

    switch (field)
    {
      case V4L2_FIELD_ANY:            return_value = "ANY"; break;
      case V4L2_FIELD_NONE:           return_value = "NONE"; break;
      case V4L2_FIELD_TOP:            return_value = "TOP"; break;
      case V4L2_FIELD_BOTTOM:         return_value = "BOTTOM"; break;
      case V4L2_FIELD_INTERLACED:     return_value = "INTERLACED"; break;
      case V4L2_FIELD_SEQ_TB:         return_value = "SEQ_TB"; break;
      case V4L2_FIELD_SEQ_BT:         return_value = "SEQ_BT"; break;
      case V4L2_FIELD_ALTERNATE:      return_value = "ALTERNATE"; break;
      case V4L2_FIELD_INTERLACED_TB:  return_value = "INTERLACED_TB"; break;
      case V4L2_FIELD_INTERLACED_BT:  return_value = "INTERLACED_BT"; break;
      default:                        return_value = "unknown"; break;
    }

    return return_value;
}

const char * v4l2_memory_to_string( enum v4l2_memory memory )
{
  const char * return_value;

  switch (memory)
  {
    case V4L2_MEMORY_MMAP:    return_value = "MMAP"; break;
    case V4L2_MEMORY_USERPTR: return_value = "USERPTR"; break;
    case V4L2_MEMORY_OVERLAY: return_value = "OVERLAY"; break;
    default:                  return_value = "unknown"; break;
  }

  return return_value;
}
static void print_v4l2_buffer( struct v4l2_buffer * buffer )
{


  /*
   * u32 index
   * enum v4l2_buf_type type
   * u32 bytesused
   * u32 flags
   * enum b4l2_field field
   * struct timeval timestamp
   * struct v4l2_timecode timecode
   * u32 sequence
   * enum v4l2_memory memory
   * union m (u32 offset)
   * u32 length
   * u32 input
   * u32 reserved
   */
  printf( "v4l2_buffer: index=%d, type=%s, bytesused=%u, flags=0x%8.8X, field=%s, sequence=%u, memory=%s, m=%u, length=%u\n",
      buffer->index,
      v4l2_buf_type_to_string( buffer->type ),
      buffer->bytesused,
      buffer->flags,
      v4l2_field_to_string( buffer->field ),
      buffer->sequence,
      v4l2_memory_to_string( buffer->memory ),
      buffer->m.offset,
      buffer->length );

  return;
}

static void print_mmap_results( int fd )
{
  struct v4l2_requestbuffers  request_buffers;
  struct my_buffer_t
  {
      struct v4l2_buffer        characteristics;
      void *                    buffer;
  } *                         buffers;
  size_t                      i;
  bool                        buffer_ok;
  struct v4l2_buffer          dequeue_buffer;
  struct timespec             start_time;
  struct timespec             end_time;

  memset( &request_buffers, 0, sizeof(request_buffers) );
  request_buffers.type    = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  request_buffers.memory  = V4L2_MEMORY_MMAP;
  request_buffers.count   = 4;

  if (ioctl( fd, VIDIOC_REQBUFS, &request_buffers) >= 0)
  {
    printf( "video buffers available: %d\n", request_buffers.count );
    buffers = calloc( request_buffers.count, sizeof(*buffers) ); // allocate and 0-out an array of buffers
    if (buffers != NULL)
    {
      buffer_ok = true;
      for (i = 0; (i < request_buffers.count) && buffer_ok; i++)
      {
        buffers[i].characteristics.type   = request_buffers.type;
        buffers[i].characteristics.memory = V4L2_MEMORY_MMAP;
        buffers[i].characteristics.index  = i;

        if (ioctl( fd, VIDIOC_QUERYBUF, &buffers[i].characteristics ) >= 0)
        {
          buffers[i].buffer = mmap( NULL, buffers[i].characteristics.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, buffers[i].characteristics.m.offset );
          if (buffers[i].buffer != MAP_FAILED)
          {
            printf( "got buffer %zu\n", i );
            print_v4l2_buffer( &buffers[i].characteristics );
            buffer_ok = true;
          }
          else
          {
            printf( "could not map buffer %zu\n", i );
            buffer_ok = false;
          }
        }
        else
        {
          printf( "could not determine the characteristics for buffer %zu\n", i );
          buffer_ok = false;
        }
      }

      if (buffer_ok)
      {
        printf( "trying to grab a frame\n" );
        clock_gettime( CLOCK_REALTIME, &start_time );
        dequeue_buffer = buffers[0].characteristics;
        print_v4l2_buffer( &dequeue_buffer );
        if (ioctl( fd, VIDIOC_QBUF, &dequeue_buffer ) >= 0)
        {
          print_v4l2_buffer( &dequeue_buffer );
          printf( "enqueued a frame\n" );

          ioctl( fd, VIDIOC_STREAMON, &dequeue_buffer.type );

          memset( &dequeue_buffer, 0, sizeof(dequeue_buffer) );
          dequeue_buffer.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
          dequeue_buffer.memory = V4L2_MEMORY_MMAP;
          print_v4l2_buffer( &dequeue_buffer );
          if (ioctl( fd, VIDIOC_DQBUF, &dequeue_buffer) >= 0)
          {
            printf( "dequeued a frame\n" );
            print_v4l2_buffer( &dequeue_buffer );
            clock_gettime( CLOCK_REALTIME, &end_time );

            print_time_difference( &start_time, &end_time );
          }
          else
          {
            char error_buffer[256];

            strerror_r( errno, error_buffer, sizeof(error_buffer) );
            printf( "could not dequeue a frame (%s)\n", error_buffer );
            print_v4l2_buffer( &dequeue_buffer );
          }
        }
        else
        {
          char error_buffer[256];

          strerror_r( errno, error_buffer, sizeof(error_buffer) );
          printf( "could not enqueue a frame (%s)\n", error_buffer );
          print_v4l2_buffer( &buffers[0].characteristics );
        }
      }
      else
      {
        printf( "not trying to grab a frame\n" );
      }

      printf( "freeing buffers\n" );
      dequeue_buffer.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
      ioctl( fd, VIDIOC_STREAMOFF, &dequeue_buffer.type );  // not strictly necessary since no buffers were enqueued
      while (i != 0)
      {
        munmap( buffers[i-1].buffer, buffers[i-1].characteristics.length );
        i--;
      }
      free( buffers );
    }
    else
    {
      printf( "could not allocate buffers\n" );
    }
  }
  else
  {
    printf( "could not request video buffers\n" );
  }
  printf( "\n" );

  return;
}
#endif

static int delete_jpegs_in_dir(const char *dirpath) {
      DIR *dir = opendir(dirpath);
      if (!dir) { perror("opendir"); return -1; }
      
      struct dirent *de;
      int deleted = 0;
      while ((de = readdir(dir)) != NULL) {
        const char *name = de->d_name;
        size_t len = strlen(name);
        int is_jpeg = 0;
        if (len >= 4 && strcasecmp(name + len - 4, ".jpg") == 0) is_jpeg = 1;
        if (len >= 5 && strcasecmp(name + len - 5, ".jpeg") == 0) is_jpeg = 1;
        if (!is_jpeg) continue;
        
        char full[512];
        int n = snprintf(full, sizeof(full), "%s/%s", dirpath, name);
        if (n < 0 || n >= (int)sizeof(full)) {
          fprintf(stderr, "Path too long, skipping: %s", name);
          continue;
        }
        
        if (unlink(full) == 0) {
          deleted++;
        } else {
          perror("unlink");
        }
      }
      
      closedir(dir);
      return deleted;
}

int main( int argc, char *argv[] )
{
  int                     fd;
  struct v4l2_format      format;
  int                     ioctl_result;
  //FILE *                  outFile;
  //unsigned char *         data;
  //struct timespec         start_time;
  //struct timespec         end_time;
  const char *video_device = "/dev/video0";
  const char *out_dir = "../chicken-cnn-c/c-infer/tmp"; //default

  if (argc >= 2)
  {
    video_device = argv[1];
  }
  if (argc >= 3)
  {
    out_dir = argv[2];
  }

  fd = open( video_device, O_RDWR, 0 );
  if (fd >= 0)
  {
    print_querycap( fd );

    print_enuminput( fd );

    print_enum_fmt_and_framesizes( fd );

    print_format( fd, &format );

    print_frameintervals( fd );

#if 1
    /*
     * ask the driver if it can do a different format
     */
    format.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
#if 1
    /* works */
    format.fmt.pix.width        = 1920;
    format.fmt.pix.height       = 1080;
#elif 1
    /* works */
    format.fmt.pix.width        = 1024;
    format.fmt.pix.height       = 768;
#elif 0
    /* works, but questionable exposure (auto-exposure might not be working right) */
    format.fmt.pix.width        = 640;
    format.fmt.pix.height       = 480;
#elif 0
    /* works, but questionable exposure (auto-exposure might not be working right) */
    format.fmt.pix.width        = 320;
    format.fmt.pix.height       = 240;
#else
    /* works, but questionable exposure (auto-exposure might not be working right) */
    format.fmt.pix.width        = 160;
    format.fmt.pix.height       = 120;
#endif
    format.fmt.pix.field = V4L2_FIELD_NONE;
    format.fmt.pix.pixelformat  = V4L2_PIX_FMT_MJPEG; // Changed to JPEG
    format.fmt.pix.colorspace   = V4L2_COLORSPACE_DEFAULT;
    ioctl_result = ioctl( fd, VIDIOC_S_FMT, &format );
    if (ioctl_result >= 0)
    {
      printf( "format proposal accepted\n" );
    }
    else
    {
      printf( "ioctl error %d\n", __LINE__ );
    }

    /*
     * see if I can use memory mapped I/O
     */
//    print_mmap_results( fd );

    /*
     * let's see if setting the time per frame (as is done is OpenCV) has an effect
     */
    {
      struct v4l2_streamparm streamparm ={0};

      streamparm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
      streamparm.parm.capture.timeperframe.numerator = 1;
      streamparm.parm.capture.timeperframe.denominator = 30;
      printf( "FPS (%d, %d) = %d/%d\n",
          ioctl( fd, VIDIOC_S_PARM, &streamparm ),
          ioctl( fd, VIDIOC_G_PARM, &streamparm ),
          streamparm.parm.capture.timeperframe.numerator,
          streamparm.parm.capture.timeperframe.denominator );
    }

    /*
     * grab an image and save it to a file
     */
     
    #define FRAME_COUNT 8
    
    mkdir(out_dir, 0755);
    int del = delete_jpegs_in_dir(out_dir);
    printf("Deleted %d existing JPEGs in %s\n", del, out_dir);
    
    // Request & map 4 buffers
    struct v4l2_requestbuffers req = {0};
    req.count = 4;
    req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;
    if (ioctl(fd, VIDIOC_REQBUFS, &req) < 0) {
      perror("VIDIOC_REQBUFS");
      close(fd); return 1;
    }
    
    struct {
      void* start;
      size_t length;
    } bufs[4] = {0};
    
    for (unsigned i=0; i<req.count; i++) {
      struct v4l2_buffer b = {0};
      b.type = req.type;
      b.memory = V4L2_MEMORY_MMAP;
      b.index = i;
      if (ioctl(fd, VIDIOC_QUERYBUF, &b) < 0) { perror("VIDIOC_QUERYBUF"); return 1; }
      bufs[i].length = b.length;
      bufs[i].start = mmap(NULL, b.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, b.m.offset);
      if (bufs[i].start == MAP_FAILED) { perror("mmap"); return 1; }
    }
    
    // Queue them now
    for (unsigned i=0; i<req.count; i++) {
      struct v4l2_buffer b = {0};
      b.type = req.type;
      b.memory = V4L2_MEMORY_MMAP;
      b.index = i;
      if (ioctl(fd, VIDIOC_QBUF, &b) < 0 ) { perror("VIDIOC_QBUF"); return 1; }
    }
    
    // Start streaming
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (ioctl(fd, VIDIOC_STREAMON, &type) < 0) { perror("VIDIOC_STREAMON"); return 1; }
    
    // Capture a loop
    for (int f = 0; f < FRAME_COUNT; f++) {
      struct v4l2_buffer b = {0};
      b.type = req.type;
      b.memory = V4L2_MEMORY_MMAP;
      
      if (ioctl(fd, VIDIOC_DQBUF, &b) < 0) { perror("VIDIOC_DQBUFF"); break; }
    
      // Save the frame
      char path[256];
      if (format.fmt.pix.pixelformat == V4L2_PIX_FMT_MJPEG) {
        // Save raw JPEG bytes
        snprintf(path, sizeof(path), "%s/frame_%02d.jpg", out_dir, f);
        FILE* fp = fopen(path, "wb");
        if (fp) { fwrite(bufs[b.index].start, 1, b.bytesused, fp); fclose(fp); }
        printf("Saved %s (%u bytes)\n", path, b.bytesused);
      } else {
        printf("Unhandled pixel format, not saved!");
     }
     
     // Requeue the buffer
     if (ioctl(fd, VIDIOC_QBUF, &b) < 0) { perror("VIDIOC_QBUF(re)"); break; }
    }
    
    // Stop and map
    ioctl(fd, VIDIOC_STREAMOFF, &type);
    for (unsigned i=0; i<req.count; i++) {
      if (bufs[i].start) munmap(bufs[i].start, bufs[i].length);
    }
     
    /*
    data = malloc( format.fmt.pix.sizeimage );
    printf( "grabbing a frame\n" );
    clock_gettime( CLOCK_REALTIME, &start_time );
    if (read( fd, data, format.fmt.pix.sizeimage ) == format.fmt.pix.sizeimage)
    {
      clock_gettime( CLOCK_REALTIME, &end_time );

      print_time_difference( &start_time, &end_time );

      printf( "saving file\n" );
      start_time = end_time;
      outFile = fopen( "raspicam_image.ppm", "wb" );
      if (outFile != NULL)
      {
        fprintf( outFile, "P6\n" );
        fprintf( outFile, "%d %d 255\n", format.fmt.pix.width, format.fmt.pix.height );
        fwrite( data, 1, format.fmt.pix.sizeimage, outFile );
        printf( "Image saved at raspicam_image.ppm\n" );

        fclose( outFile );

        clock_gettime( CLOCK_REALTIME, &end_time );

        print_time_difference( &start_time, &end_time );
      }
      else
      {
        printf( "unable to open file\n" );
      }
    }
    else
    {
      printf( "unable to read image data\n" );
    }
    */
#endif

    close( fd );
  }
  else
  {
    printf( "unable to open %s\n", video_device );
  }

  return 0;
}

#undef PRINT_STUFF
